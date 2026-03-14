// =====================================================
// Module: TRIMMOMATIC — Adapter Trimming & Quality Filtering
// =====================================================

process TRIMMOMATIC {
    tag "${meta.id}"
    label 'process_medium'
    publishDir "${params.outdir}/trimmomatic/${meta.id}", mode: 'copy', overwrite: true,
        saveAs: { filename ->
            if (filename.endsWith('.log')) "logs/$filename"
            else filename
        }

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*_paired_{1,2}.fastq.gz"), emit: trimmed_reads
    tuple val(meta), path("*_unpaired_{1,2}.fastq.gz"), emit: unpaired_reads, optional: true
    tuple val(meta), path("*.trimmomatic.log"),         emit: log
    path "versions.yml",                                emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args        = task.ext.args   ?: 'LEADING:3 TRAILING:3 SLIDINGWINDOW:4:15'
    def prefix      = task.ext.prefix ?: "${meta.id}"
    def threads     = task.cpus
    def adapter_cmd = params.trimmomatic_adapter ?
        "ILLUMINACLIP:${params.trimmomatic_adapter}:2:30:10:2:True" : ''
    def minlen      = "MINLEN:${params.min_trim_length}"
    """
    # Run Trimmomatic PE
    trimmomatic PE \\
        -threads ${threads} \\
        -phred33 \\
        ${reads[0]} ${reads[1]} \\
        ${prefix}_paired_1.fastq.gz   ${prefix}_unpaired_1.fastq.gz \\
        ${prefix}_paired_2.fastq.gz   ${prefix}_unpaired_2.fastq.gz \\
        ${adapter_cmd} \\
        ${args} \\
        ${minlen} \\
        2> ${prefix}.trimmomatic.log

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        trimmomatic: \$(trimmomatic -version)
    END_VERSIONS
    """

    stub:
    """
    touch ${meta.id}_paired_1.fastq.gz
    touch ${meta.id}_paired_2.fastq.gz
    touch ${meta.id}_unpaired_1.fastq.gz
    touch ${meta.id}_unpaired_2.fastq.gz
    echo "Trimmomatic stub log" > ${meta.id}.trimmomatic.log

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        trimmomatic: 0.39
    END_VERSIONS
    """
}
