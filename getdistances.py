import requests
import pymysql
import json

# For every unique unordered pair of rides in a given park, get the distance
# between those two attractions, following valid pathways in the park.

from ia626fpconn import getConnInfo, getDirectionsAPIKey
MYSQL_CONN = getConnInfo()
conn = pymysql.connect(host=MYSQL_CONN["HOST"], port=MYSQL_CONN["PORT"], user=MYSQL_CONN["USER"],
                       passwd=MYSQL_CONN["PASS"], db=MYSQL_CONN["DB"], autocommit=True)
cur = conn.cursor(pymysql.cursors.DictCursor)

# Get all parks that have rides (ie have a parent)
parkids = []
entrances = {}
cur.execute("SELECT * FROM Parks WHERE parentid IS NOT NULL")
for row in cur:
    #print(f"{row['name']} ({row['parkid']})")
    parkids.append(row['parkid'])
    gate = {}
    gate['lat'] = float(row['gatelat'])
    gate['lon'] = float(row['gatelon'])
    entrances[row['parkid']] = gate

# For each pair of attractions, get the walking distance between them.
# To save on API calls, storage, and processing time, pairs of attractions are
#   unordered. For consistency, the attractions are inserted into the database
#   in alphabetical order by attraction ID.

'''
parkids = [
    '47f90d2c-e191-4239-a466-5892ef59a88b'
]
'''
#routes = 0

MAPS_API_URL = f"https://maps.googleapis.com/maps/api/directions/json?key={getDirectionsAPIKey()}&mode=walking"

for parkid in parkids:
    attractions = {}
    cur.execute(f"SELECT * FROM Attractions WHERE parkid = '{parkid}'")
    for row in cur:
        #print(row["attractionid"])
        a = {}
        a["name"] = row["name"]
        a["slug"] = row["slug"]
        a["type"] = row["type"]
        a["lat"] = float(row["lat"])
        a["lon"] = float(row["lon"])
        a["parkid"] = row["parkid"]
        attractions[row['attractionid']] = a
        #attractions[row['attractionid']] = attractions[row['attractionid']].pop("attractionid")
    #print(attractions.keys())
    routes = 0
    for i in attractions.keys():
        for j in attractions.keys():
            if i < j:
                #routes += 1
                # Try to find the distance in the database
                cur.execute(f"SELECT * FROM Distances WHERE attraction_a = '{i}' AND attraction_b = '{j}'")
                if cur.rowcount == 0:
                    print(f"{attractions[i]['lat']},{attractions[i]['lon']};{attractions[j]['lat']},{attractions[j]['lon']}")
                    url = MAPS_API_URL+f"&origin={attractions[i]['lat']},{attractions[i]['lon']}&destination={attractions[j]['lat']},{attractions[j]['lon']}"
                    print(url)
                    r = requests.get(url) # UNCOMMENT TO RUN API -- COSTS REAL WORLD MONEY
                    data = json.loads(r.text)
                    if data['status'] == "OK":
                        distance = data['routes'][0]['legs'][0]["distance"]["value"]
                        insertsql = f'''INSERT INTO Distances (attraction_a, attraction_b, distance)
                            VALUES ("{i}", "{j}", "{distance}");'''
                        cur.execute(insertsql)
                    else:
                        print("Directions API error")
                        print(data['status'])
                    routes += 1
                else:
                    print("Found in DB")
#print(routes)
