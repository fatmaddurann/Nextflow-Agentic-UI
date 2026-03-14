// =====================================================
// Module: STAR — Genome Index Generation & RNA-Seq Alignment
// =====================================================


process STAR_GENOMEGENERATE {
    tag "genome_index"
    label 'process_high'
    publishDir "${params.outdir}/star_index", mode: 'copy', overwrite: true

    input:
    path genome_fasta
    path gtf

    output:
    path "star_index",   emit: index
    path "versions.yml", emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args    = task.ext.args ?: ''
    def threads = task.cpus
    def mem_gb  = (task.memory.toGiga() * 0.8).intValue()
    """
    # Validate inputs
    if [ ! -s "${genome_fasta}" ]; then
        echo "ERROR: Genome FASTA file is empty or not found: ${genome_fasta}" >&2
        exit 1
    fi

    # Build STAR index
    mkdir -p star_index

    STAR \\
        --runMode genomeGenerate \\
        --runThreadN ${threads} \\
        --genomeDir star_index \\
        --genomeFastaFiles ${genome_fasta} \\
        --sjdbGTFfile ${gtf} \\
        --sjdbOverhang 100 \\
        --genomeSAindexNbases 14 \\
        --limitGenomeGenerateRAM ${mem_gb}000000000 \\
        ${args}

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        star: \$(STAR --version | sed -e "s/STAR_//g")
    END_VERSIONS
    """

    stub:
    """
    mkdir -p star_index
    touch star_index/Genome
    touch star_index/SA
    touch star_index/SAindex

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        star: 2.7.11a
    END_VERSIONS
    """
}


process STAR_ALIGN {
    tag "${meta.id}"
    label 'process_high'
    publishDir "${params.outdir}/star_align/${meta.id}", mode: 'copy', overwrite: true,
        saveAs: { filename ->
            if (filename.endsWith('.bam'))      "bam/$filename"
            else if (filename.contains('Log'))  "logs/$filename"
            else if (filename.endsWith('.tab')) "junction/$filename"
            else filename
        }

    input:
    tuple val(meta), path(reads)
    path  index
    path  gtf

    output:
    tuple val(meta), path("*Aligned.sortedByCoord.out.bam"), emit: bam
    tuple val(meta), path("*Log.final.out"),                 emit: log_final
    tuple val(meta), path("*Log.out"),                       emit: log_out
    tuple val(meta), path("*Log.progress.out"),              emit: log_progress
    tuple val(meta), path("*SJ.out.tab"),                    emit: sj, optional: true
    path "versions.yml",                                     emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args    = task.ext.args   ?: ''
    def prefix  = task.ext.prefix ?: "${meta.id}"
    def threads = task.cpus
    def reads1  = reads[0]
    def reads2  = reads[1]
    def mem_gb  = (task.memory.toGiga() * 0.8).intValue()
    """
    # Validate STAR index
    if [ ! -d "${index}" ] || [ -z "\$(ls -A ${index})" ]; then
        echo "ERROR: STAR index directory is missing or empty: ${index}" >&2
        echo "TIP: Run STAR_GENOMEGENERATE first, or provide --star_index path" >&2
        exit 1
    fi

    # Run STAR alignment
    STAR \\
        --runMode alignReads \\
        --runThreadN ${threads} \\
        --genomeDir ${index} \\
        --readFilesIn ${reads1} ${reads2} \\
        --readFilesCommand zcat \\
        --outSAMtype BAM SortedByCoordinate \\
        --outSAMattributes NH HI AS NM MD \\
        --outFileNamePrefix ${prefix}. \\
        --outSAMunmapped Within \\
        --outSAMstrandField intronMotif \\
        --sjdbGTFfile ${gtf} \\
        --quantMode GeneCounts \\
        --limitBAMsortRAM ${mem_gb}000000000 \\
        --outBAMsortingBinsN 50 \\
        --twopassMode Basic \\
        ${args}

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        star: \$(STAR --version | sed -e "s/STAR_//g")
    END_VERSIONS
    """

    stub:
    """
    touch ${meta.id}.Aligned.sortedByCoord.out.bam
    touch ${meta.id}.Log.final.out
    touch ${meta.id}.Log.out
    touch ${meta.id}.Log.progress.out
    touch ${meta.id}.SJ.out.tab

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        star: 2.7.11a
    END_VERSIONS
    """
}
