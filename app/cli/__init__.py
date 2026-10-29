"""Flask CLI command groups: `flask schema ...`, `flask users ...`, `flask jobs ...`,
`flask bans ...`, `flask images ...` and `flask riot ...`."""


def register_cli(app):
    """Attach the project's command groups to `app.cli`."""
    from app.cli.schema import schema_cli
    app.cli.add_command(schema_cli)
    from app.cli.users import users_cli
    app.cli.add_command(users_cli)
    from app.cli.jobs import jobs_cli
    app.cli.add_command(jobs_cli)
    from app.cli.bans import bans_cli
    app.cli.add_command(bans_cli)
    from app.cli.images import images_cli
    app.cli.add_command(images_cli)
    from app.cli.riot import riot_cli
    app.cli.add_command(riot_cli)
