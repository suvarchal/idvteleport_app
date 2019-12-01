import os
from celery import Celery, chain, group, task
import docker
# Create the app and set the broker location (RabbitMQ)
redis_host = os.getenv('REDIS_HOST',"localhost")
app = Celery('teleport_worker',
             backend=f'redis://{redis_host}:6379/0',
             broker=f'redis://{redis_host}:6379/0')

docker_client = docker.from_env() 

# add echo start and end date
teleport_isl = """<?xml version="1.0" encoding="ISO-8859-1"?>
<isl debug="true" offscreen="false">
   <bundle file="{bundle}" timedriverstart="{starttime}" timedriverend="{endtime}" wait="true"/>
   <pause seconds="30"/>
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
                                        entryid=entryid
                                        ))
    
    # bind mount mount_dir in container 
    mount_dst = os.path.join("/", os.path.basename(mount_dir))
    working_dir = mount_dst
    print(os.path.abspath(mount_dir)) 
    # this kind of session dir mounting doesnt work if upload directory is docker volume
    # then we need to mount entire upload directory
    #volumes = {os.path.abspath(mount_dir): {'bind': mount_dst, 'mode':'rw'}} 
    volumes = {os.path.dirname(os.path.abspath(mount_dir)): {'bind': "/uploads", 'mode':'rw'}} 
    working_dir = os.path.join("/uploads", os.path.basename(mount_dir))
        

    command = f"xvfb-run /IDV/runIDV -islinteractive {os.path.basename(isl_file)}"
    user = "1000:1000"
    # command_fail = "xvfb-run /IDV/runIDV "
    # if detach=False (default) call is blocking and success can be known by output 
    # tty is required
    # if detach=True then status messages can be updates
    detach = True
    container_out = docker_client.containers.run('suvarchal/idvheadless', tty=True,
                                                 command=command,
                                                 volumes=volumes,
                                                 detach=detach,
                                                 working_dir=working_dir,
                                                 remove=True)
    if detach:
        for line in container_out.logs(stream=True):
            #print(line.strip())
            self.update_state(state=line.strip().decode('utf-8'))
    
    return container_out.logs().decode('utf-8') # use publish string ?
if __name__ == "__main__":
    app.start()
