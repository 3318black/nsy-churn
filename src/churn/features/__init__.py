"""Construction of the training grid and of its features.

``windows``
    Rolling window aggregates over the event journal. Every value answers one
    question: what did we know strictly before ``T0``?
``build``
    Observation grid, target and feature matrix.

The rule both modules exist to uphold: a feature computed for
``(client_id, T0)`` uses only events strictly earlier than ``T0``.
"""

__all__: list[str] = []
