"""Input side of the pipeline: contract, validation, sources and generator.

The modules of this package are ordered by dependency.

``schemas``
    Executable declaration of ``docs/data-contract.md``, sections 1 and 2. It is
    the single place where the column list, the closed event nomenclature and
    the distinction between the mandatory core and the optional columns live.
``validate``
    Vectorised check of the contract invariants, with a blocking failure and a
    report naming every offending invariant.
``sources``
    Single source interface every origin of data implements, plus the Parquet
    reader and writer shared by all of them.
``synthetic``
    Generator of raw timestamped events, used by the automated tests. See
    decisions D3 and D14.
"""

__all__: list[str] = []
