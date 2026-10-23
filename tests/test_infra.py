"""Static checks on the container and IaC files (they are built and linted, never deployed here):
non-root container with a healthcheck, managed identity with one least-privilege role, no secrets."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENAI_USER = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"


def test_dockerfile_is_multi_stage_non_root_with_a_healthcheck():
    d = (ROOT / "Dockerfile").read_text()
    froms = re.findall(r"^FROM (\S+)", d, re.M)
    assert len(froms) == 2 and froms[0].startswith("node:") and froms[1].startswith("python:")
    assert all(re.search(r":\d+\.\d+\.\d+", f) for f in froms), froms        # exact versions
    assert re.search(r"^USER optix$", d, re.M) and "HEALTHCHECK" in d and "/healthz" in d
    assert not re.search(r"(?i)(api[_-]?key|secret|password)\s*=", d)
    ignore = (ROOT / ".dockerignore").read_text().split()
    assert {".env", ".env.*", ".git", ".venv"} <= set(ignore)


def test_compose_binds_localhost_and_reads_env_from_an_optional_file():
    c = (ROOT / "docker-compose.yml").read_text()
    assert '"127.0.0.1:8000:8000"' in c and "required: false" in c and "read_only: true" in c


def test_bicep_uses_a_managed_identity_and_one_least_privilege_role():
    b = (ROOT / "infra" / "main.bicep").read_text()
    assert "type: 'SystemAssigned'" in b
    assert b.count("Microsoft.Authorization/roleAssignments@") == 1 and OPENAI_USER in b
    assert "scope: openAi" in b and "principalType: 'ServicePrincipal'" in b
    assert "Microsoft.Insights/components@" in b and "Microsoft.OperationalInsights/workspaces@" in b
    assert "Microsoft.App/managedEnvironments@" in b and "Microsoft.App/containerApps@" in b
    # no key for the model: no listKeys on the OpenAI account, no API key setting
    assert "openAi.listKeys" not in b and "AZURE_OPENAI_API_KEY" not in b
    assert "allowInsecure: false" in b and "path: '/healthz'" in b


def test_bicep_params_hold_no_secret_values():
    lines = [l for l in (ROOT / "infra" / "main.bicepparam").read_text().splitlines() if not l.strip().startswith("//")]
    assert not re.search(r"(?i)(key|secret|password|connection)", "\n".join(lines))


def test_nothing_in_the_repo_runs_a_deploy():
    runners = [ROOT / ".github" / "workflows" / "ci.yml", *(ROOT / "tools").glob("*.py")]
    bad = ("az deployment", "az group create", "az containerapp", "azd up", "docker push")
    hits = [f"{f.name}: {w}" for f in runners for w in bad if w in f.read_text()]
    assert not hits, hits
