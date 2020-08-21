### Script to download events (using antelope data base api) from locally mounted nfs share to hardy
"""
Note if you have been given this as an example of how to use antelope please note that it is pretty messy and I now know with hindsight that there are better ways to do this. Specifically
1. Always invoke command line tools where possible because they work better and are more completely documented than the python lib
2. As I see it the place for the python lib is to just get simple pieces of information (like time, evid etc.) out of antelope tables
3. If I were to rewrite this program it would open the reno dbmaster, use the evid to determine the event time, then export all of the data to SAC (or miniseed) using trexcerp command, after
which a subset of station information would be exported from the reno dbmaster db using db2stationxml
"""
import sys
import os
import json
import time
import math # for great circle calculation
import subprocess
###antelope python dependencies
"""
Ipython instructions:
    1. source antelope
    2. activate antelope anaconda env

"""
envPath = '/opt/antelope/5.6'
sys.path.append( envPath + '/data/python' )
#sys.path.append( os.environ['ANTELOPE'] + '/data/python' )
from antelope.datascope import *
"""
Gets the origin info using the /data/dbnv reno orgin table that gabe makes
returns location, data and time
"""
def getOriginLatLon(evid,dbPath):
    """
    pass
    FROM THE DOCS:
    with closing(dbopen('/opt/antelope/data/db/demo/demo', 'r')) as db:
        dbtable = db.lookup(table='arrival')
        dbtable.record = 0
        print dbtable.getv('sta', 'chan')
        print dbtable.getv('auth', table='origin')
        print(dbtable.record_count)
    """
    """
    Steps:
    1.get origin table
    2.get the event
    3. get the lat, lon and date from the event
    db = dbopen(dbPath,'r')
    """
    with closing(dbopen(dbPath,'r')) as db:
        db_table=db.lookup(database=None,table='origin',field=None,record=None)
        #there should only be one record
        #db_view.record_count
        db_view = db_table.subset("evid == "+str(evid))
        db_view.record=0
        return db_view.getv('lat','lon','time','orid')

def getStationsInRadius(dbPath,latCenter,lonCenter,stationRadius=100):
    """
    Steps:
    1. Open the site table
    2. Iterate through the site table to determine if the station is in the radius
    3. return this list of stations
    """
    with closing(dbopen(dbPath,'r')) as db:
        lat,lon = 0,0
        siteList = [] 
        db = dbopen(dbPath,'r')
        db_table = db.lookup(table="site")
        #now join it to the sensor table (for channel) and sensor model table (for sensor model)
        db_table = db_table.join('sensor')
        db_table = db_table.join('instrument')
        #iterate through all of these and determine if the lat an lon is within
        for dbrecord in db_table.iter_record():
            lat,lon = dbrecord.getv('lat','lon')      
            if(latLonInRadius(lat,lon,latCenter,lonCenter,stationRadius)):
                siteList.append((dbrecord.getv('sta'),dbrecord.getv('chan'),dbrecord.getv('instype')))
        #note that a lot of duplicate data is put into this list because of my table joining, so I have to clean it up a little bit
        siteList = list(set(siteList))
    return siteList

"""
This is not how this functions should work, use this code but as the get waveforms function
steps:
1.copy wolfdisc to working directory wolfdisc
2.Copy the site table and all of the other crap to the current working direcotry
3.Execute db2sd and turn the whole damin thing into one seed archive
4. deal with the seed archive
"""

def getTraces(stationList,timeGMT,dbPath,preEventTime,postEventTime,dbName='reno',evid=0,orid=-1,distance=100.0/111.0,nSeconds = 60):
    #gets all of the traces for the given station for this event
    distance = distance/111.0 #approximate the number of degrees (about 111 km per degree on earth)
    recordCount = 0
    timeStruct = time.gmtime(timeGMT)
    print("Note that this doesnt currently work for events that are occuring at the time that the data base switches over to a new day! \n")
    #correct the year day to use the 00 and 0 format used by our database
    yday = timeStruct.tm_yday
    if(yday < 10):
        yday = "00" + str(yday)
    elif(yday >= 10 and yday < 100):
        yday = "0" + str(yday)
    else:
        yday = str(yday)
    dbPath = DBROOT + str(timeStruct[0]) + '/' + yday + "/"
    #save all of the data asscoiated with this event (cd to data base dir and save back results to current working dir)    
    #Try again with arid, see if you can get it to download the correct time (instead of 10 minutes before it is supposed to download)
    #trexcerpt -m event -o sc -s 'evid == 523696'  reno /home/dukeleto/git/getEventsAntelope/scratch/out \ time time+5
    command = "cd "+ dbPath + " && " + "trexcerpt -m event -o sc -s " +"'evid == " + str(evid) + "' " +  "reno " + os.getcwd() +"/scratch/out \ time time+"+str(nSeconds)
    #    command = "cd "+ dbPath + " && " "trexcerpt -m event -v -o sc -w " + os.getcwd() + "'%{" +str(orid)+"}/%' " + dbName + " " + os.getcwd()+"/out " + "'parrival()-'"+ str(preEventTime) + " " + str(preEventTime+postEventTime)   
    print(command)
    print("saving data as SAC files to the current wd\n")
    subprocess.call(command,shell=True, stdout=subprocess.PIPE)
    print("saved sac files to the current working directory (note that this has saved ALL files for the event the radius has not been applied!)")
    ### now get the station xml for the whole network (just do it this way because it is easier than doing it individually and not that much larger than doing it individually)
    subprocess.call("db2stationxml -s " + '"B.*"'+" -L response -o reno.xml /usr/local/data/renomaster/reno",shell=True, stdout=subprocess.PIPE)
            
#checks if the given lat and lon is in circle given the center point and the radius
def latLonInRadius(lat,lon,latCenter,lonCenter,radius):
    #just do it using the great circle formula https://en.wikipedia.org/wiki/Great-circle_distance
    RADIUS_EARTH = 6371.0
    #compute the distance between the points
    distanceDegrees = math.acos(math.sin(math.radians(lat))*math.sin(math.radians(latCenter))
     + math.cos(math.radians(lat))*math.cos(math.radians(latCenter))*math.cos(math.radians(lon-lonCenter)))
    if(distanceDegrees * RADIUS_EARTH <= radius):
        return True
    return False

#begining of main function
stationRadius = 30 #radius to get stations (given in KM)
DBROOT = "/usr/local/data/"
EVID = 385392 #MOGUL event
orid = -1 #note that I cannot hard code an orgin ID since it can change if the event is ever relocated (while the event id 
preEventTime = 10
postEventTime = 60
stationsList = []
#variables changed within this function
#fetch the lat,lon,time and ORID of the event using the master reno orgin table
locationInformation = getOriginLatLon(EVID,DBROOT +'dbnv/reno')
#get the stations (and channels) that should have recorded this event within my radius--note that this function needs the site table
stationsList = getStationsInRadius(DBROOT +'renomaster/reno',locationInformation[0],locationInformation[1],stationRadius)
#convert the time into an time struct
timeGMT = locationInformation[2]
orid = locationInformation[3]
#get traces for all stations within the station radius
### note that allot of the stuff going into this is probably redundent
getTraces(stationsList,timeGMT,DBROOT,preEventTime,postEventTime,'reno',EVID,orid,stationRadius)

