#!/usr/bin/env nextflow
// =====================================================
// Nextflow-Agentic-UI — RNA-Seq Pipeline (DSL2)
// Steps: FastQC → Trimmomatic → STAR → featureCounts → MultiQC
// =====================================================

nextflow.enable.dsl = 2


include { FASTQC as FASTQC_RAW     } from './modules/fastqc'
include { FASTQC as FASTQC_TRIMMED } from './modules/fastqc'
include { TRIMMOMATIC         } from './modules/trimmomatic'
include { STAR_GENOMEGENERATE } from './modules/star'
include { STAR_ALIGN          } from './modules/star'
include { SAMTOOLS_SORT       } from './modules/samtools'
include { SAMTOOLS_INDEX      } from './modules/samtools'
include { FEATURECOUNTS       } from './modules/featurecounts'
include { MULTIQC             } from './modules/multiqc'


workflow {

    // Log pipeline start info
    log.info """
    ╔══════════════════════════════════════════════════════╗
    ║       Nextflow-Agentic-UI  |  RNA-Seq Pipeline       ║
    ╠══════════════════════════════════════════════════════╣
    ║  reads       : ${params.reads}
    ║  outdir      : ${params.outdir}
    ║  genome      : ${params.genome ?: 'not provided'}
    ║  gtf         : ${params.gtf ?: 'not provided'}
    ║  star_index  : ${params.star_index ?: 'will be built'}
    ║  max_cpus    : ${params.max_cpus}
    ║  max_memory  : ${params.max_memory}
    ╚══════════════════════════════════════════════════════╝
    """.stripIndent()

    // Input Channel: paired-end FASTQ reads
    Channel
        .fromFilePairs( params.reads, checkIfExists: !workflow.stubRun )
        .map { sample_id, reads ->
            def meta = [
                id          : sample_id,
                single_end  : false,
                strandedness: 'forward'
            ]
            [ meta, reads ]
        }
        .set { ch_reads }

    // Step 1: FastQC (raw reads quality check)
    fastqc_html    = Channel.empty()
    fastqc_zip     = Channel.empty()
    fastqc_version = Channel.empty()

    if ( !params.skip_fastqc ) {
        FASTQC_RAW( ch_reads )
        fastqc_html    = FASTQC_RAW.out.html
        fastqc_zip     = FASTQC_RAW.out.zip
        fastqc_version = FASTQC_RAW.out.versions
    }

    // Step 2: Trimmomatic (adapter trimming & quality filtering)
    trim_reads     = ch_reads
    trim_log       = Channel.empty()
    trim_version   = Channel.empty()

    if ( !params.skip_trimming ) {
        TRIMMOMATIC( ch_reads )
        trim_reads   = TRIMMOMATIC.out.trimmed_reads
        trim_log     = TRIMMOMATIC.out.log
        trim_version = TRIMMOMATIC.out.versions

        // FastQC on trimmed reads (post-trimming QC)
        if ( !params.skip_fastqc ) {
            FASTQC_TRIMMED( trim_reads.map { meta, reads -> [ meta + [id: "${meta.id}.trimmed"], reads ] } )
        }
    }

    // Step 3: STAR genome index (build if not provided)
    star_index = Channel.empty()

    if ( params.star_index ) {
        // Use pre-built index
        star_index = Channel.value( file(params.star_index, checkIfExists: !workflow.stubRun) )
    } else if ( params.genome && params.gtf ) {
        // Build STAR index on-the-fly
        STAR_GENOMEGENERATE(
            file(params.genome, checkIfExists: !workflow.stubRun),
            file(params.gtf,    checkIfExists: !workflow.stubRun)
        )
        star_index = STAR_GENOMEGENERATE.out.index
    } else if ( !workflow.stubRun ) {
        error """
        ERROR: Either --star_index OR both --genome and --gtf must be provided.
        Tip: Pre-build a STAR index using:
             nextflow run main.nf --genome /path/genome.fa --gtf /path/genes.gtf
        """
    } else {
        star_index = Channel.value( file('STUB_INDEX') )
    }

    // Step 4: STAR alignment
    bam_sorted   = Channel.empty()
    align_log    = Channel.empty()
    align_version = Channel.empty()

    if ( !params.skip_alignment ) {
        STAR_ALIGN(
            trim_reads,
            star_index,
            file(params.gtf ?: 'STUB_GTF', checkIfExists: !workflow.stubRun)
        )
        align_log     = STAR_ALIGN.out.log_final
        align_version = STAR_ALIGN.out.versions

        // Step 5: SAMtools sort & index
        SAMTOOLS_SORT( STAR_ALIGN.out.bam )
        SAMTOOLS_INDEX( SAMTOOLS_SORT.out.bam )
        bam_sorted = SAMTOOLS_SORT.out.bam
    }

    // Step 6: featureCounts (gene-level quantification)
    counts_matrix = Channel.empty()

    bam_sorted
        .map { meta, bam -> [ meta, bam ] }
        .collect { it }
        .set { ch_bam_for_counting }

    FEATURECOUNTS(
        bam_sorted.collect { it[1] },
        file(params.gtf ?: 'STUB_GTF', checkIfExists: !workflow.stubRun)
    )
    counts_matrix = FEATURECOUNTS.out.counts

    // Step 7: MultiQC (aggregate QC report)
    multiqc_files = Channel.empty()
    multiqc_files = multiqc_files.mix(
        fastqc_zip.collect { it[1] }.ifEmpty([]),
        trim_log.collect   { it[1] }.ifEmpty([]),
        align_log.collect  { it[1] }.ifEmpty([])
    )

    MULTIQC( multiqc_files.collect() )

    // Completion summary
    workflow.onComplete {
        def status = workflow.success ? "SUCCESS" : "FAILED"
        def duration = workflow.duration
        log.info """
        ╔══════════════════════════════════════════════════════╗
        ║   Pipeline Completed  |  Status: ${status}
        ╠══════════════════════════════════════════════════════╣
        ║  Duration   : ${duration}
        ║  Exit status: ${workflow.exitStatus}
        ║  Work dir   : ${workflow.workDir}
        ║  Output dir : ${params.outdir}
        ║  Errors     : ${workflow.errorMessage ?: 'none'}
        ╚══════════════════════════════════════════════════════╝
        """.stripIndent()

        if ( workflow.success ) {
            log.info "Results available at: ${params.outdir}"
        } else {
            log.error "Pipeline FAILED — check AI agent logs at: ${params.outdir}/pipeline_info/execution_report.html"
        }
    }
}
