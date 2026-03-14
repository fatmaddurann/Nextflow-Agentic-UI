// =====================================================
// Module: SAMTOOLS — Sort & Index BAM Files
// =====================================================


process SAMTOOLS_SORT {
    tag "${meta.id}"
    label 'process_medium'
    publishDir "${params.outdir}/samtools/${meta.id}", mode: 'copy', overwrite: true

    input:
    tuple val(meta), path(bam)

    output:
    tuple val(meta), path("*.sorted.bam"), emit: bam
    path "versions.yml",                   emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args   = task.ext.args   ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def mem_per_thread = (task.memory.toMega() / task.cpus / 2).intValue()
    """
    # Sort BAM by coordinate
    samtools sort \\
        ${args} \\
        -@ ${task.cpus} \\
        -m ${mem_per_thread}M \\
        -o ${prefix}.sorted.bam \\
        ${bam}

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: \$(echo \$(samtools --version 2>&1) | sed 's/^.*samtools //; s/Using.*\$//')
    END_VERSIONS
    """

    stub:
    """
    touch ${meta.id}.sorted.bam

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: 1.18
    END_VERSIONS
    """
}


process SAMTOOLS_INDEX {
    tag "${meta.id}"
    label 'process_single'
    publishDir "${params.outdir}/samtools/${meta.id}", mode: 'copy', overwrite: true

    input:
    tuple val(meta), path(bam)

    output:
    tuple val(meta), path("*.bai"), emit: bai
    path "versions.yml",            emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Index sorted BAM
    samtools index \\
        -@ ${task.cpus} \\
        ${bam}

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: \$(echo \$(samtools --version 2>&1) | sed 's/^.*samtools //; s/Using.*\$//')
    END_VERSIONS
    """

    stub:
    """
    touch ${bam}.bai

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: 1.18
    END_VERSIONS
    """
}
