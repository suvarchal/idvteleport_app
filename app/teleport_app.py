import os
import re
import subprocess
import string 
import random
from flask import Flask, url_for, request, session, jsonify
from flask import redirect, render_template, g, flash
from werkzeug.utils import secure_filename
import teleport_worker
from teleport_worker import check_run
from celery import group
app = Flask(__name__)
app.config.from_pyfile('settings.py')

# move imports to on the fly improve response time

@app.route('/', methods=['GET'])
def index_get():
    
    if request.method == 'GET':
        name = request.args.get('name','noname')
        session['name'] = name 
    return render_template('index.html')


def allowed_file(filename):
    """ quick checks if the file is in ALLOWED_EXTENSIONS """ 
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_bundle(filename):
    """ Check if the bundle used a time driver """
    with open(os.path.join(g.user_dir, filename)) as f:
        bundle_data = f.read()
    return True if re.findall('UsesTimeDriver', bundle_data) else False

def publish(filename, entryid=None):
    """ publishes file and returns publish parent entryid """
    """ we have to go into uplods folder to publish """
    from urllib.parse import urlparse, parse_qs

    filepath = os.path.join(g.user_dir,filename)
    if entryid:
        pargs = ['ramadda_publish', filepath, '-entryid', entryid]
    else:
        pargs = ['ramadda_publish', filepath]
    # publish cannot publish files outside of current directory so 
    # using ugly cd and shell for now 
    publish_status = subprocess.check_output([f"cd {os.path.abspath(g.user_dir)};ramadda_publish {filename}"], shell=True)
    
    published_link = publish_status.decode().splitlines()[-1].split()[-1] # gets location 
    entryid = parse_qs(urlparse(published_link).query)['entryid'][0]
    return entryid

def validate_datetime(tdate):
    from datetime import datetime
    valid_date = False
    for fmt in ['%Y%m%d', '%Y-%m-%d']:
        try:
            parsed_date = datetime.strptime(tdate, fmt)
        except ValueError:
            pass
        else:
            # to accepatable string format for teleport
            # change this date for hours minutes seconds
            valid_date = parsed_date.strftime('%Y-%m-%d 00:00:00')  
    return valid_date

def validate_timedelta(tdate):
    """ only matches integer, so careful with YYYYMMDD """
    td = False
    try:
        td = int(tdate)
    except ValueError:
        td = False
    return td


def validate_form(form_data):
    """ validates the form 
        with side effects -- flash messages
    """
    from datetime import datetime, timedelta
    lines = form_data.splitlines()
    
    errors = False
    for lino,li in enumerate(lines):
        dates=li.strip().split()
        if not (len(dates) == 2 or len(dates) == 6):
            flash(f'Error in line:{lino+1}: Wrong number of arguments.'
                  'each line should have atleast 2 arguments seperated by space'
                  'startdate enddate or middate and timedelta in integer number of days'
                  'optionally specify bounds in order North West South East')
            errors = True
            continue
        start_date = validate_datetime(dates[0])
        if not start_date:
            flash(f'Error in line:{lino+1}: '
                  'Date must be in format YYYY-MM-DD or YYYYMMDD') 
            errors = True
        # end date can also be date not just td
        # clean this up
        # 
        end_date = validate_timedelta(dates[1]) or validate_datetime(dates[1])
        if not end_date:
            flash(f'Error in line:{lino}: '
                  'second argument should be end date in format YYYY-MM-DD or'
                  'time duration in integer number of days.')
            errors = True
        # validate north west south east
    return errors


@app.route('/', methods=['POST'])
def index_post():
    """ responds to post request 
        would be good to validate form as and when entered using JS
        but it is fine to do it this way
    """
    from datetime import datetime, timedelta

    teleport_form = request.form['teleport-form']
    bundle = request.files.get('bundle-file', '')
    
    print(teleport_form)
    
    # clean this directory later?
    # directory later user_id will be stored in session
    user_id = "".join(random.choice(string.ascii_lowercase) for x in range(8))
    g.user_dir = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
   
    try:
        os.makedirs(g.user_dir)
    # retry just incase if randomly directory exists, should write this better
    except FileExistsError:
        user_id = "".join(random.choice(string.ascii_lowercase) for x in range(8))
        g.user_dir = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
        os.makedirs(g.user_dir)

    # first validate the bundle
    bundle_errors = False
    if bundle: 
        if allowed_file(bundle.filename):          
            filename = secure_filename(bundle.filename)
            bundle.save(os.path.join(g.user_dir, filename))
            if not validate_bundle(filename):
                flash(f'{filename} does not use a time driver.'
                      ' Using a time driver is necessary' 
                      'to teleport a bundle. See this video to set one: https://www.youtube.com/watch?v=Q0xHPfmW-JM')
                bundle_errors = True
                # delete the directory
                #g.user_dir = os.path.join(app.config['UPLOAD_FOLDER'], user_id)ink()
        else:
            flash(f'{bundle.filename} is not a valid IDV xidv bundle file?')
            bundle_errors = True
    else:
        flash('No file attached')
    
    # validate datetime form 
    form_errors = validate_form(teleport_form)

    if form_errors or bundle_errors:
        return render_template('index.html', saved_form=teleport_form)
    
    # store user_id in session after all checks pass 
    # so that we can display status on next get request.
    session['user_id'] = user_id
    g.user_id = user_id
    
    # publish the uploaded bundle to rammadda to get entryid.
    # it can be disirable to do this after jobs are successfully submitted. 
    entryid = publish(filename)

    # calling second time to get dates but
    # getting dates is redundant when we use JS to make requests to validate form
    # form was validated above so all values(start and end dates) must be present 
    # no need to check again 
    celery_jobs = []
    for li in teleport_form.splitlines():
        dates = li.strip().split()
        starttime = validate_datetime(dates[0])
        
        if validate_datetime(dates[1]):
             endtime = validate_datetime(dates[1])
        # check if second argument is int number of days
        elif validate_timedelta(dates[1]):
            endtime = datetime.strptime(starttime, '%Y-%m-%d %H:%M:%S') + timedelta(days=int(dates[1]))
            endtime = endtime.strftime('%Y-%m-%d 00:00:00')
        # skip if above dont work
        else:
            continue
        # check if datetime or if int check if date is of type yyyymmdd        
        
        # date and time  
        #casename = "_".join([os.path.basename(bundle.filename).split('.')[0],"_".join(starttime.split()),"_".join(endtime.split())])
        #only date
        casename = "_".join([os.path.basename(bundle.filename).split('.')[0],starttime.split()[0],endtime.split()[0]])
        # add bbox info , do this above 
        if len(dates)>2:
            bbox = ",".join(dates[2:])
        else: 
            bbox = None
        # submit jobs to the celery workers
        celery_jobs.append(check_run.s(g.user_dir,bundle.filename,casename,starttime,endtime,bbox,entryid))
    
    job_run = group(celery_jobs).delay()
    
    #if not job_run.status == 'FAILURE':
    #    flash('something awful happend, server is busy with other jobs')
    #    return render_template('index.html', saved_form=teleport_form)
    # publish inital files to get the directory
    # return jsonify({'entryid':entryid})
    return redirect(f'https://weather.rsmas.miami.edu/repository/entry/show?entryid={entryid}',302)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
