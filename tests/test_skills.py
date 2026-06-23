"""Tests du système de skills UNION IA."""

import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cerveau.skills.gestionnaire import GestionnaireSkills
from cerveau.skills.excel import SkillExcel
from cerveau.skills.pdf import SkillPDF
from cerveau.skills.access import SkillAccess


def test_lister_skills():
    g = GestionnaireSkills()
    skills = g.lister()
    assert len(skills) >= 4
    ids = {s['id'] for s in skills}
    assert 'pdf' in ids
    assert 'excel' in ids
    assert 'access' in ids
    assert 'word' in ids


def test_skill_csv():
    g = GestionnaireSkills()
    with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False, encoding='utf-8') as f:
        f.write("nom,age,ville\nLouis,17,Paris\nAlice,25,Lyon\n")
        p = Path(f.name)
    result = g.traiter_fichier(p)
    p.unlink()
    assert result is not None
    assert 'nom' in result
    assert 'Louis' in result


def test_skill_csv_tsv():
    excel = SkillExcel()
    with tempfile.NamedTemporaryFile(suffix='.tsv', mode='w', delete=False, encoding='utf-8') as f:
        f.write("col1\tcol2\nA\tB\nC\tD\n")
        p = Path(f.name)
    contenu = excel.extraire(p)
    p.unlink()
    assert 'col1' in contenu
    assert 'A' in contenu


def test_skill_fichier_inconnu():
    g = GestionnaireSkills()
    with tempfile.NamedTemporaryFile(suffix='.xyz', mode='w', delete=False) as f:
        f.write("test")
        p = Path(f.name)
    result = g.traiter_fichier(p)
    p.unlink()
    assert result is None  # pas de skill pour .xyz


def test_skill_fichier_absent():
    g = GestionnaireSkills()
    result = g.traiter_fichier(Path('/tmp/fichier_qui_nexiste_pas.pdf'))
    assert result is None


def test_custom_skill_ajouter_supprimer():
    with tempfile.TemporaryDirectory() as tmp:
        custom_path = Path(tmp) / 'skills.json'
        g = GestionnaireSkills(custom_path=custom_path)
        res = g.ajouter_custom({
            'nom': 'Test Skill',
            'extensions': ['test'],
            'description': 'Un skill de test',
            'commande': 'echo {fichier}',
        })
        assert 'id' in res
        sid = res['id']
        skills = g.lister()
        custom = [s for s in skills if s.get('type') == 'custom']
        assert len(custom) == 1
        assert custom[0]['nom'] == 'Test Skill'
        ok = g.supprimer_custom(sid)
        assert ok
        skills2 = g.lister()
        custom2 = [s for s in skills2 if s.get('type') == 'custom']
        assert len(custom2) == 0


def test_custom_skill_persistance():
    with tempfile.TemporaryDirectory() as tmp:
        custom_path = Path(tmp) / 'skills.json'
        g1 = GestionnaireSkills(custom_path=custom_path)
        g1.ajouter_custom({'nom': 'Persist', 'extensions': ['p'], 'commande': 'echo {fichier}'})
        g2 = GestionnaireSkills(custom_path=custom_path)
        custom = [s for s in g2.lister() if s.get('type') == 'custom']
        assert len(custom) == 1
        assert custom[0]['nom'] == 'Persist'


def test_pdf_peut_traiter():
    skill = SkillPDF()
    assert skill.peut_traiter(Path('test.pdf'))
    assert not skill.peut_traiter(Path('test.xlsx'))


def test_access_peut_traiter():
    skill = SkillAccess()
    assert skill.peut_traiter(Path('test.db'))
    assert skill.peut_traiter(Path('test.sqlite'))
    assert skill.peut_traiter(Path('test.accdb'))
    assert not skill.peut_traiter(Path('test.pdf'))
