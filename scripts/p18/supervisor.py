"""One P18 runtime using accepted guards and real detector/spatial traffic."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import types

from evidence import ROOT, REPO, PACKAGE, PREVIOUS, save, utc, inventory, digest

def load_spatial_supervisor():
    path=PREVIOUS/'stop_b_map_frame_spatial_chain/spatial_runtime.py'
    source=path.read_text()
    replacements={
        "REPO/'outputs/evidence/07_lidar_icp_stationary_gate/gate.py'": "PREVIOUS/'07_lidar_icp_stationary_gate/gate.py'",
        "REPO/'outputs/evidence/07_lidar_icp_motion_acceptance_resume/snapshot.py'": "PREVIOUS/'07_lidar_icp_motion_acceptance_resume/snapshot.py'",
    }
    for old,new in replacements.items():
        assert source.count(old)==1
        source=source.replace(old,new)
    module=types.ModuleType('p18_accepted_spatial_supervisor')
    module.__file__=str(path)
    module.PREVIOUS=PREVIOUS
    exec(compile(source,str(path),'exec'),module.__dict__)
    module.snapshot.WORLD=str(REPO/'ros2_ws/install/aegisinspect_sim/share/aegisinspect_sim/worlds/inspection_bay.sdf')
    save(PACKAGE/'provenance/supervisor_reuse.json',{'original':str(path),'sha256':digest(path),'path_only_replacements':replacements,'world_path_override':module.snapshot.WORLD,'scientific_modules':'All detector, projection, tf2, P15, P16 and P17 implementations resolve from merged P18.'})
    return module

accepted=load_spatial_supervisor()
from sensor_msgs.msg import Imu
from std_srvs.srv import Trigger
from rclpy.qos import qos_profile_sensor_data
from rclpy.serialization import serialize_message
from ament_index_python.packages import get_package_prefix

class P18Runtime(accepted.SpatialRuntime):
    def __init__(self):
        self.start_response_ns=None
        self.imu_count=0
        super().__init__()
        self.results['safety']={'P13_START_CALL_COUNT':0,'RESET_CALL_COUNT':0,'P18_RUNTIME_INVOCATIONS':1,'LOCALIZATION_SCIENTIFIC_ACCEPTANCE_RERUN':False,'REPEATABILITY_RUN':False,'GT_OPERATIONAL_USE':'NO'}
        self.create_subscription(Imu,'/aegis/sensors/imu/data',self.imu,qos_profile_sensor_data)
        accepted.base.TOPICS.append('/aegis/sensors/imu/data')

    def imu(self,msg,info):
        self.imu_count+=1
        assert msg.header.frame_id=='imu_link'
        if self.imu_count<=3:
            (PACKAGE/'sensors'/f'imu_{self.imu_count}.cdr').write_bytes(serialize_message(msg))
        self.log('imu',stamp_ns=accepted.base.stamp(msg.header.stamp),frame_id=msg.header.frame_id,gid=accepted.base.gid(info.get('publisher_gid')))

    def launch(self,name,argv,runtime=True):
        if name=='spatial_detector':
            argv=list(argv)
            argv[2]=str(PACKAGE/'runtime/harness/p18_worker.py')
            proc=super().launch(name,argv,runtime)
            self.bounded(lambda:(ROOT/'worker_ready.json').is_file(),30,'DETECTOR_INITIALIZATION_FAILED')
            self.graph_sample()
            self.ownership.require_operational(self.gids)
            assert self.graph_valid()
            assert not self.graph['topics']['/aegis/sim/ground_truth/pose']['subscriptions']
            assert self.imu_count>0
            self.gazebo_identity_guard.require_bound()
            client=self.create_client(Trigger,'/aegis/sim/motion/start')
            self.bounded(client.service_is_ready,5,'P18_START_SERVICE_UNAVAILABLE')
            invocation={'utc':utc(),'service':'/aegis/sim/motion/start','request':{},'invocation_count':1,'simulation_stamp_ns':self.samples['clock'][-1]['stamp_ns'],'purpose':'P18 first integration; not a localization scientific acceptance rerun'}
            with (ROOT/'start_invocation.json').open('x') as stream:
                json.dump(invocation,stream,indent=2)
                stream.flush();os.fsync(stream.fileno())
            self.results['safety']['P13_START_CALL_COUNT']=1
            future=client.call_async(Trigger.Request())
            self.bounded(future.done,5,'P18_START_TIMEOUT_NO_RETRY')
            response=future.result()
            self.start_response_ns=self.samples['clock'][-1]['stamp_ns']
            save(ROOT/'start_response.json',{'utc':utc(),'success':response.success,'message':response.message,'simulation_stamp_ns':self.start_response_ns,'invocation_count':1})
            assert response.success,'P18_START_REJECTED_NO_RETRY'
            # Wait through P13's initial hold before allowing the first selected
            # observation. This is scheduling only, not altered inference semantics.
            save(ROOT/'detector_release.json',{'minimum_observation_stamp_ns':self.start_response_ns+3_000_000_000})
            self.destroy_client(client)
            print('P18_START_ACCEPTED_COUNT=1 RESET_COUNT=0',flush=True)
            return proc
        return super().launch(name,argv,runtime)

    def run(self):
        # The inherited accepted supervisor proves sensors, ICP/adapter, exact
        # timestamped TF and genuine DET-FINAL-v1 -> depth -> map -> P15.
        super().run()
        self.runtime_complete=False
        (ROOT/'active_runtime_result.json').rename(ROOT/'spatial_stage_result.json')
        assert self.start_response_ns is not None
        assert self.mapped[0]['map_projection']['stamp_ns']>=self.start_response_ns+3_000_000_000
        self.phase='p16_p17_live_handoff'
        downstream=self.launch('p16_p17_handoff',['/tmp/aegis-stopb-p16p17.J0c6Zg/venv/bin/python','-B',str(PACKAGE/'runtime/harness/p18_downstream.py')],runtime=False)
        self.bounded(lambda:downstream.poll() is not None,45,'P16_P17_HANDOFF_TIMEOUT')
        assert downstream.returncode==0,'P16_P17_HANDOFF_FAILED'
        assert json.loads((ROOT/'downstream_complete.json').read_text())['PASS']
        self.phase='dashboard_browser'
        self.launch('dashboard',['env','AEGISINSPECT_DB_PATH='+str(PACKAGE/'p16/p18.sqlite3'),'/tmp/aegis-stopb-p16p17.J0c6Zg/venv/bin/python','-B','-m','streamlit','run',str(REPO/'dashboard/app.py'),'--server.address=127.0.0.1','--server.port=8518','--server.headless=true','--server.fileWatcherType=none','--browser.gatherUsageStats=false'])
        browser=self.launch('dashboard_capture',['/tmp/aegis-stopb-p16p17.J0c6Zg/venv/bin/python','-B',str(PACKAGE/'runtime/harness/p18_browser.py')],runtime=False)
        self.bounded(lambda:browser.poll() is not None,75,'DASHBOARD_BROWSER_CAPTURE_TIMEOUT')
        assert browser.returncode==0,'DASHBOARD_BROWSER_CAPTURE_FAILED'
        assert (PACKAGE/'p16/dashboard/real_dashboard_ready.png').is_file()
        self.phase='p13_completion_window'
        self.bounded(lambda:self.samples['clock'][-1]['stamp_ns']>=self.start_response_ns+21_000_000_000,60,'P13_COMPLETION_WINDOW_TIMEOUT')
        self.graph_sample()
        self.snapshot()
        self.ownership.require_operational(self.gids)
        assert self.graph_valid()
        edges={}
        for row in self.samples['tf_static']:
            edge=(row['parent'],row['child'])
            edges.setdefault(edge,set()).add(row['gid'])
        sensor_edges={('base_link','lidar_link'),('base_link','imu_link'),('base_link','camera_link'),('camera_link','camera_optical_frame')}
        for edge in sensor_edges:
            assert len(edges[edge])==1
            assert self.gids[next(iter(edges[edge]))]=='/aegis/robot_state_publisher'
        assert not self.graph['topics']['/aegis/sim/ground_truth/pose']['subscriptions']
        save(PACKAGE/'tf/ownership.json',{'operational':[{'parent':p,'child':c,'gids':sorted(g),'owners':[self.gids[x] for x in sorted(g)]} for (p,c),g in self.ownership.edges.items()],'sensors':[{'parent':p,'child':c,'gids':sorted(edges[(p,c)]),'owners':[self.gids[x] for x in sorted(edges[(p,c)])]} for p,c in sorted(sensor_edges)],'competing_owner_count':0,'PASS':True})
        save(PACKAGE/'runtime/p13_state.json',{'START_calls':1,'RESET_calls':0,'START_response':json.loads((ROOT/'start_response.json').read_text()),'final_observed_simulation_stamp_ns':self.samples['clock'][-1]['stamp_ns'],'completion_window_observed':True,'state_interpretation':'COMPLETE inferred from accepted START, continuous simulator liveness, and frozen 20-second state-machine schedule; no separate state topic exists.','trajectory_source_sha256':digest(REPO/'ros2_ws/src/aegisinspect_sim/src/deterministic_motion_system.cpp'),'scientific_localization_evaluation_rerun':False})
        save(PACKAGE/'runtime/final_ros_graph.json',self.graph)
        self.check_kernel('pre_shutdown')
        assert not self.errors,self.errors
        self.runtime_complete=True
        self.results.update(runtime_evidence_complete_utc=utc(),mapped_defect_id=self.mapped[0]['P15_record']['defect_id'],imu_count=self.imu_count)
        save(ROOT/'active_runtime_result.json',{'pass':True,**self.results})
        print('P18_FULL_RUNTIME_CHAIN_CAPTURE_COMPLETE=YES',flush=True)

def verify_integrity_before_capture():
    """Complete blocking Git checks before ROS init or live subscriptions exist."""
    assert subprocess.check_output(['git','status','--short'],cwd=REPO,text=True)=='', 'P18_WORKTREE_NOT_CLEAN'
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    assert head==json.loads((ROOT/'assets.json').read_text())['p18_head'], 'P18_HEAD_MISMATCH'
    result={'utc':utc(),'head':head,'worktree_clean':True,'completed_before_ros_init':True}
    save(PACKAGE/'git/pre_capture_integrity.json',result)
    return result

def main():
    gate=json.loads((REPO/'outputs/evidence/stop_b_p18_integration_base/base_gate_result.json').read_text())
    assert gate['classification']=='P18 INTEGRATION BASE — PASS'
    before=inventory()
    save(PACKAGE/'runtime/pre_launch_processes.json',before)
    if before['count']:
        print('RELEVANT_RESIDUAL_PROCESS_COUNT='+str(before['count']),flush=True)
        return 90
    integrity=verify_integrity_before_capture()
    with (ROOT/'runtime_invocation.json').open('x') as stream:
        json.dump({'utc':utc(),'pid':os.getpid(),'single_runtime_only':True,'p18_head':integrity['head']},stream,indent=2)
        stream.flush();os.fsync(stream.fileno())
    save(ROOT/'runtime_before.json',before)
    save(PACKAGE/'runtime/package_prefixes.json',{name:get_package_prefix(name) for name in ['aegisinspect_description','aegisinspect_sim','aegisinspect_localization','aegisinspect_mapping','aegisinspect_perception','aegisinspect_interfaces','rtabmap_odom','ros_gz_bridge']})
    accepted.rclpy.init(args=[])
    node=None
    try:
        node=P18Runtime()
        node.run()
    except Exception as exc:
        if node is not None:
            node.runtime_complete=False
            node.fail(str(exc))
        (ROOT/'exception.txt').write_text(traceback.format_exc())
        print('P18_RUNTIME_BLOCKED='+str(exc),flush=True)
    finally:
        if node is not None:
            node.shutdown()
            node.destroy_node()
        accepted.rclpy.try_shutdown()
    return 0 if node is not None and node.results['runtime_pass'] and node.results['RELEVANT_RESIDUAL_PROCESS_COUNT']==0 else 1

if __name__=='__main__':
    raise SystemExit(main())
