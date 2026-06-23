"""Tests du système d'authentification UNION IA."""

import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cerveau.auth import Auth


def _auth():
    tmp = tempfile.mkdtemp()
    return Auth(db_path=Path(tmp) / 'auth_test.db')


def test_admin_cree_automatiquement():
    a = _auth()
    users = a.lister_utilisateurs()
    admins = [u for u in users if u['role'] == 'admin']
    assert len(admins) >= 1


def test_creer_compte():
    a = _auth()
    u = a.creer_compte('test@example.com', 'motdepasse123', 'Test')
    assert u['email'] == 'test@example.com'
    assert u['role'] == 'user'


def test_email_doublon():
    a = _auth()
    a.creer_compte('dup@example.com', 'mdp123')
    try:
        a.creer_compte('dup@example.com', 'autremdp')
        assert False, "Doit lever ValueError"
    except ValueError as e:
        assert 'déjà utilisé' in str(e)


def test_mdp_trop_court():
    a = _auth()
    try:
        a.creer_compte('court@example.com', '12345')
        assert False
    except ValueError as e:
        assert 'court' in str(e)


def test_connexion_valide():
    a = _auth()
    a.creer_compte('user@test.fr', 'secret42', 'User')
    token = a.connecter('user@test.fr', 'secret42')
    assert token is not None
    assert len(token) > 20


def test_connexion_mauvais_mdp():
    a = _auth()
    a.creer_compte('x@test.fr', 'bonmdp')
    token = a.connecter('x@test.fr', 'mauvaismdp')
    assert token is None


def test_valider_token():
    a = _auth()
    a.creer_compte('v@test.fr', 'mdp123', 'V')
    token = a.connecter('v@test.fr', 'mdp123')
    u = a.valider_token(token)
    assert u is not None
    assert u['email'] == 'v@test.fr'
    assert u['role'] == 'user'


def test_token_invalide():
    a = _auth()
    u = a.valider_token('token_bidon_123')
    assert u is None


def test_deconnecter():
    a = _auth()
    a.creer_compte('d@test.fr', 'mdp123')
    token = a.connecter('d@test.fr', 'mdp123')
    a.deconnecter(token)
    u = a.valider_token(token)
    assert u is None


def test_changer_role():
    a = _auth()
    u = a.creer_compte('r@test.fr', 'mdp123', 'R')
    a.changer_role(u['id'], 'admin')
    users = a.lister_utilisateurs()
    found = next((x for x in users if x['email'] == 'r@test.fr'), None)
    assert found and found['role'] == 'admin'


def test_supprimer_utilisateur():
    a = _auth()
    u = a.creer_compte('sup@test.fr', 'mdp123')
    a.supprimer_utilisateur(u['id'])
    users = a.lister_utilisateurs()
    assert not any(x['email'] == 'sup@test.fr' for x in users)
