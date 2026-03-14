// =====================================================
// Module: FEATURECOUNTS — Gene-Level Read Quantification
// =====================================================

process FEATURECOUNTS {
    tag "all_samples"
    label 'process_medium'
    publishDir "${params.outdir}/featurecounts", mode: 'copy', overwrite: true

    input:
    path bam_files
    path gtf

    output:
    path "featureCounts.txt",           emit: counts
    path "featureCounts.txt.summary",   emit: summary
    path "versions.yml",                emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args        = task.ext.args ?: ''
    def feature     = params.featurecounts_type ?: 'exon'
    def attribute   = params.featurecounts_id   ?: 'gene_id'
    def paired_flag = '-p'  // Paired-end flag
    def bam_list    = bam_files instanceof List ? bam_files.join(' ') : bam_files
    """
    # Validate GTF annotation
    if [ ! -s "${gtf}" ]; then
        echo "ERROR: GTF annotation file is empty or not found: ${gtf}" >&2
        echo "TIP: Download from Ensembl or GENCODE for your genome build" >&2
        exit 1
    fi

    # Run featureCounts
    featureCounts \\
        ${paired_flag} \\
        -T ${task.cpus} \\
        -t ${feature} \\
        -g ${attribute} \\
        -a ${gtf} \\
        -o featureCounts.txt \\
        --extraAttributes gene_name,gene_biotype \\
        --countReadPairs \\
        -B \\
        -C \\
        ${args} \\
        ${bam_list}

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        subread: \$(echo \$(featureCounts -v 2>&1) | sed -e "s/featureCounts v//g")
    END_VERSIONS
    """

    stub:
    """
    echo -e "Geneid\tChr\tStart\tEnd\tStrand\tLength\tsample1.bam" > featureCounts.txt
    echo -e "ENSG00000001\tchr1\t100\t200\t+\t100\t50" >> featureCounts.txt
    echo "Status\tsample1.bam" > featureCounts.txt.summary
    echo "Assigned\t10000" >> featureCounts.txt.summary

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        subread: 2.0.6
    END_VERSIONS
    """
}
