import os
from celery import Celery, chain, group, task
import docker
# Create the app and set the broker location (RabbitMQ)
app = Celery('teleport_worker',
             backend='redis',
             broker='redis://localhost:6379/1')

docker_client = docker.from_env() 

# add echo start and end date
teleport_isl = """<?xml version="1.0" encoding="ISO-8859-1"?>
<isl debug="true" offscreen="false">
   <bundle file="{bundle}" timedriverstart="{starttime}" timedriverend="{endtime}" wait="true"/>
   <pause/>
   <movie file="{casename}.gif" capture="legend" framerate="1" imagequality="1.0" endframepause="2" />
   <group loop="1" sleep="60.0minutes">
      <displayproperties display="class:ucar.unidata.idv.control.ColorPlanViewControl">
         <property name="DisplayAreaSubset"  value="true"/>
      </displayproperties>
      <export file="{casename}.zidv" what="zidv" />
   </group>
   <exec command="ramadda_publish {casename}.zidv -a {casename}.gif -entryid {entryid}"/>
   <jython code="exit()"/>
</isl>
"""
# bundle, casename, starttime, endtime



@app.task
def publish(filepath):
    """ publish file async 
    """
    return None

@app.task(bind=True)
def check_run(self, mount_dir, bundle='NOAA_sst.xidv', casename='NOAA_sst', starttime='2001-06-01 00:00:00', endtime='2001-09-01 00:00:00', entryid=""):
    
    # use relative path because we want to run isl in volume mounted container
    isl_file = os.path.join(os.path.relpath(mount_dir), casename+".isl")

    with open(os.path.join(mount_dir, casename+".isl"),'wt') as f:
       f.writelines(teleport_isl.format(bundle=bundle, 
                                        casename=casename,
                                        starttime=starttime,
                                        endtime=endtime,
                                        entryid=entryid))
    
    # bind mount mount_dir in container 
    mount_dst = os.path.join("/", os.path.basename(mount_dir)) 
    volumes = {os.path.abspath(mount_dir): {'bind': mount_dst, 'mode':'rw'}}
    command = f"xvfb-run /IDV/runIDV -islinteractive {os.path.basename(isl_file)}"
    # command_fail = "xvfb-run /IDV/runIDV "
    # if detach=False (default) call is blocking and success can be known by output 
    # tty is required
    # if detach=True then status messages can be updates
    detach = True
    container_out = docker_client.containers.run('idv_teleport', tty=True,
                                                 command=command,
                                                 volumes=volumes,
                                                 detach=detach,
                                                 working_dir=mount_dst)
    if detach:
        for line in container_out.logs(stream=True):
            print(line.strip())
            self.update_state(state=line.strip())
    
    return container_out.logs() # use publish string ?
if __name__ == "__main__":
    app.start()
