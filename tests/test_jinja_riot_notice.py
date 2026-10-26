"""F13-g S9 (AC4): the Jinja Riot section points at the new admin area."""


class TestRiotHandoffNotice:
    def test_notice_and_link_render_for_an_admin(self, admin_client):
        html = admin_client.get('/riftbound/price').get_data(as_text=True)
        # The template uses HTML entities, so match the entity-free spans.
        assert 'gestiona ahora en la nueva administraci' in html
        assert 'La sincronizaci' in html
        assert '/riftbound/app/admin/riot' in html

    def test_plain_users_do_not_see_the_page(self, authenticated_client):
        assert authenticated_client.get('/riftbound/price').status_code == 403
