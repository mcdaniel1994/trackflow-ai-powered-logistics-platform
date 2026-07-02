"""Root wrapper for the Central API historical incident seed command."""

from central_api.domains.incidents.seed import entrypoint


if __name__ == "__main__":
    entrypoint()

