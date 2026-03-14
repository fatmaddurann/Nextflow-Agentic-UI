// =====================================================
// Module: FASTQC — Quality Control of FASTQ Reads
// =====================================================

process FASTQC {
    tag "${meta.id}"
    label 'process_low'
    publishDir "${params.outdir}/fastqc/${meta.id}", mode: 'copy', overwrite: true

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.html"), emit: html
    tuple val(meta), path("*.zip"),  emit: zip
    path "versions.yml",             emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args     = task.ext.args   ?: ''
    def prefix   = task.ext.prefix ?: "${meta.id}"
    def threads  = task.cpus
    """
    # Run FastQC
    fastqc \\
        ${args} \\
        --threads ${threads} \\
        --outdir . \\
        ${reads}

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        fastqc: \$(fastqc --version | sed 's/FastQC v//')
    END_VERSIONS
    """

    stub:
    """
    touch ${meta.id}_1_fastqc.html
    touch ${meta.id}_1_fastqc.zip
    touch ${meta.id}_2_fastqc.html
    touch ${meta.id}_2_fastqc.zip

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        fastqc: 0.11.9
    END_VERSIONS
    """
}
