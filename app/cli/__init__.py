"""Flask CLI command groups (`flask schema ...`; later units add `flask users`)."""


def register_cli(app):
    """Attach the project's command groups to `app.cli`."""
    from app.cli.schema import schema_cli
    app.cli.add_command(schema_cli)
