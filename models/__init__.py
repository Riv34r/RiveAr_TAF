"""
Models package.

Pydantic models mirroring the SUT's response schemas, one module per
domain (auth, admin, roles, product, inventory, order) plus common.py's
shared PaginatedResponse[T]/StrictModel base. Used for full-shape contract
validation (Model.model_validate(response.json())), on top of - not
instead of - the value-level assertions each domain's own tests make.
"""
