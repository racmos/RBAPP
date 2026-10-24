"""Flask CLI command groups: `flask schema ...`, `flask users ...` and `flask jobs ...`."""


def register_cli(app):
    """Attach the project's command groups to `app.cli`."""
    from app.cli.schema import schema_cli
    app.cli.add_command(schema_cli)
    from app.cli.users import users_cli
    app.cli.add_command(users_cli)
    from app.cli.jobs import jobs_cli
    app.cli.add_command(jobs_cli)
