"""Batch scoring and export, lot 6.

Four modules, four responsibilities.

``schemas``
    The contract of one exported row, section 4 of the data contract.
``scoring``
    Scores one date: ranks, deciles, actionable factors, batch identity.
``sinks``
    Writes a batch to a destination, without transforming any value.
``run_scoring``
    The command line entry point.
"""
