"""
API clients package.

One module per RiveAr domain (auth, admin, roles, products, inventory,
orders, cart, addresses), each a thin wrapper around
core.api.api_client.ApiClient that knows that domain's endpoints.
"""
