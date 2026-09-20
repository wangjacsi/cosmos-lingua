"""Exercise the real installer/loader/control plane using a local source archive."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
CORE = HERE.parent / 'cosmos-billy'
os.environ['COSMOS_HOME'] = tempfile.mkdtemp(prefix='lingua-install-validation-')
os.environ['COSMOS_LANG'] = 'en'
sys.path.insert(0, str(CORE))

from cosmos.contracts import ToolContext, hooks
from cosmos.core import agents, userstate
from cosmos.core.config import settings
from cosmos.core.control import ControlPlane
from cosmos.core.market import install, spec
from cosmos.core.orchestrator import Orchestrator
from cosmos.core.personas import Persona
from cosmos.core.registry import Registry

manifest = spec.load_manifest_file(HERE / 'cosmos-agent.yaml')['manifest']
entry = {key: manifest[key] for key in ('id','type','version','contract','title','description','author','capabilities','requires')}
entry.update(repo='https://github.com/wangjacsi/cosmos-lingua',ref='lingua-local-validation')
entry = spec.validate_index_entry(entry, official=True)['entry']
buf = io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in HERE.rglob('*'):
        relative=path.relative_to(HERE)
        if path.is_file() and not set(relative.parts)&{'tests','scripts','__pycache__','.pytest_cache','.git'}:
            archive.write(path,'bundle/'+relative.as_posix())
install._download = lambda url: buf.getvalue()  # Only transport is replaced; no network.
from cosmos.core.market import catalog
catalog.read_catalog = lambda **kwargs: {'entries':[entry]}
reg=Registry();events=[]
engine=SimpleNamespace(registry=reg,persona=Persona(),session=SimpleNamespace(user_id='local'),request_reconnect=lambda reason:events.append(reason))
control=ControlPlane(engine)
class Context(ToolContext):
    @property
    def user_id(self):return 'local'
    @property
    def lang(self):return 'en'
    @property
    def brain(self):return None
    def write_log(self,*args,**kwargs):pass
    def run_tool(self,*args,**kwargs):raise AssertionError('No external tools in installation validation')
ctx=Context();engine.tool_context=lambda:ctx;checks=[]
with userstate.scope(ctx.user_id):
    assert settings.agents_dir.is_relative_to(Path(os.environ['COSMOS_HOME']))
    disclosure=control.manage_agent(dict(op='install',id=entry['id']))
    assert disclosure.get('needs_approval') and not reg.get('lingua')
    result=control.manage_agent(dict(op='install',id=entry['id'],approve=True))
    assert result['ok'] and not result['load']['failed'],result
    plugin=reg.get('lingua');assert plugin and plugin.market_id==entry['id']
    control.set_agent_enabled(dict(name='lingua',enabled=True))
    view=control.read_agent_view('lingua')
    assert view['ok'] and any(b['type']=='html' for b in view['view']['blocks']),view
    checks.append('real archive install, loader attachment and full control-plane view')
    reply=Orchestrator.dispatch(engine,'lingua',ctx,dict(action='set',goal='Travel conversations',language='es'))
    assert 'Settings updated' in reply,reply
    assert control.read_agent_view('lingua', plugin.settings_at)['view']['params']['tab']=='settings'
    Orchestrator.dispatch(engine,'lingua',ctx,dict(action='status',_tab='today'))
    Orchestrator.dispatch(engine,'lingua',ctx,dict(action='note_word',term='Hola',meaning='Hello'))
    Orchestrator.dispatch(engine,'lingua',ctx,dict(action='layout',view_mode='practice'))
    saved=control.save_agent_settings(dict(agent='lingua',space='browser'))
    assert saved['ok'] and saved['space']['chosen']=='browser'
    assert control.read_agent_view('lingua')['view']['space']=={'allowed':['screen','window','browser'],'chosen':'browser'}
    checks.append('settings entry, language profile, expression and browser placement')
    from cosmos.core import permissions
    permissions.set_state('memory','deny')
    assert not control.read_agent_view('lingua')['ok']
    permissions.set_state('memory','allow')
    assert control.read_agent_view('lingua')['ok']
    checks.append('memory permission denial blocks the saved view; restoration reopens it')
    control.set_agent_enabled(dict(name='lingua',enabled=False))
    reply=Orchestrator.dispatch(engine,'lingua',ctx,dict(action='layout',view_mode='overview'))
    assert 'switched off' in reply and not hooks.enabled(plugin,'view',ctx.user_id)
    assert not control.read_agent_view('lingua')['ok']
    assert not hooks.enabled(plugin,'turn',ctx.user_id) and not hooks.enabled(plugin,'offer',ctx.user_id)
    assert ctx.load_agent_state('lingua-live','presentation')['view_mode']=='practice'
    control.set_agent_enabled(dict(name='lingua',enabled=True))
    assert hooks.enabled(plugin,'view',ctx.user_id) and control.read_agent_view('lingua')['ok']
    checks.append('off blocks actions and view; on restores the view')
    assert control.manage_agent(dict(op='remove',id=entry['id']))['ok']
    assert reg.get('lingua') is None and not spec.agent_dir(entry['id']).exists()
    assert 'Unknown tool' in Orchestrator.dispatch(engine,'lingua',ctx,{})
    assert 'lingua' not in Registry().discover_installed().names()
    checks.append('remove detaches package and tool; fresh registry excludes it')
    installed=control.manage_agent(dict(op='install',id=entry['id'],approve=True))
    assert installed['ok'] and not installed['load']['failed'],installed
    control.set_agent_enabled(dict(name='lingua',enabled=True))
    settings_after=control.read_agent_settings('lingua')
    assert settings_after['space']['chosen']=='browser'
    html=next(b for b in control.read_agent_view('lingua')['view']['blocks'] if b['type']=='html')
    assert html['state']['view_mode']=='practice'
    assert html['state']['goal']=='Travel conversations' and html['state']['language']=='es'
    assert html['state']['total']==1
    checks.append('reinstall retains goal, language, expression, layout and display placement')
    assert control.manage_agent(dict(op='remove',id=entry['id']))['ok']
report={'agent':entry['id'],'isolated':True,'source':'local development archive','real_external_requests':False,'checks':checks,'limits':['No installer button clicks or published-version update','No real voice, video, model or external account integration','Removal retains personal memory and preferences','Browser sign-in is separate; real cross-browser login is not verified']}
out=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/lingua-install-validation.json')
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
