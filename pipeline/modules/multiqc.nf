// =====================================================
// Module: MULTIQC — Aggregate QC Reports
// =====================================================

process MULTIQC {
    tag "all_samples"
    label 'process_single'
    publishDir "${params.outdir}/multiqc", mode: 'copy', overwrite: true

    input:
    path multiqc_files

    output:
    path "*multiqc_report.html", emit: report
    path "*_data",               emit: data
    path "versions.yml",         emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args           = task.ext.args   ?: ''
    def config         = params.multiqc_config ? "--config ${params.multiqc_config}" : ''
    def report_name    = 'multiqc_report'
    """
    # Run MultiQC across all QC files
    multiqc \\
        --force \\
        --outdir . \\
        --filename ${report_name} \\
        ${config} \\
        ${args} \\
        .

    # Capture version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        multiqc: \$(multiqc --version | sed "s/multiqc, version //")
    END_VERSIONS
    """

    stub:
    """
    touch multiqc_report.html
    mkdir -p multiqc_report_data
    touch multiqc_report_data/multiqc_general_stats.txt

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        multiqc: 1.19
    END_VERSIONS
    """
}
