import argparse
from ia626fpconn import getConnInfo
import pymysql
import numpy as np
import math

MYSQL_CONN = getConnInfo()
conn = pymysql.connect(host=MYSQL_CONN["HOST"], port=MYSQL_CONN["PORT"], user=MYSQL_CONN["USER"],
                       passwd=MYSQL_CONN["PASS"], db=MYSQL_CONN["DB"], autocommit=True)
cur = conn.cursor(pymysql.cursors.DictCursor)

def getParkSlugsNamesIDs():
    # Returns a pair of lists, all park slugs and display names
    # Names are in the format "Park Name (Destination Name)"
    # For now, only returning WDW parks since they're the only ones I have wait info for
    slugs = []
    names = []
    ids = []
    cur.execute("SELECT p.name as name, p.slug as slug, p.parkid as parkid, d.name as destname FROM Parks p, Parks d WHERE p.parentid IS NOT NULL AND p.parentid = d.parkid ORDER BY destname, name")
    for r in cur:
        if r["parkid"] in ["75ea578a-adc8-4116-a54d-dccb60765ef9", "47f90d2c-e191-4239-a466-5892ef59a88b", "288747d1-8b4f-4a64-867e-ea7c9b27bad8", "1c84a229-8862-4648-9c71-378ddd2c7693"]:
            slugs.append(r['slug'])
            names.append(f"{r['name']} ({r['destname']})")
            ids.append(r['parkid'])
    return slugs, names, ids

def h(todois, currenti, distmatrix):
    # Nearest Neighbor heuristic algorithm
    if len(todois) == 1:
        tofrom = sorted([currenti, todois[0]])
        return distmatrix[tofrom[0]][tofrom[1]]
    elif len(todois) == 0:
        return 0
    mind = None
    minc = None
    for d in todois:
        if mind == None:
            mind = d
            tofrom = sorted([currenti, d])
            minc = distmatrix[tofrom[0]][tofrom[1]]
        else:
            tofrom = sorted([currenti, d])
            c = distmatrix[tofrom[0]][tofrom[1]]
            if c < minc:
                mind = d
                minc = c
    # Remove minimum destination from the todo list
    newtodo = [d for d in todois if d != mind]
    return minc + h(newtodo, mind, distmatrix)

def sort_queue(queue):
    nqueue = sorted(queue, key=lambda n: n['heur'])
    #nqueue = queue.copy()
    #nqueue.sort(key=lambda x,y: cmp(x['heur']+x['cost'], y['heur']+y['cost']))
    #if (nqueue != queue):
        #print("Shuffled list order")
    return nqueue

def wait_cost(a, time):
    global cur
    hour = math.floor(time/60)
    cur.execute("SELECT AVG(waittime) as wait FROM Queue WHERE attractionid = %s AND type = %s AND HOUR(queuedt) = %s", [a, "STANDBY", hour])
    row = None
    wait = 0
    for r in cur:
        row = r
    if row["wait"] is None:
        # Assume it's a show or a batch load thing
        # Take half the duration, since that's the average time
        # that you'll have to wait for the batch to finish
        cur.execute("SELECT duration FROM Attractions WHERE attractionid = %s", a)
        for dr in cur:
            wait = float(dr["duration"])/2
    else:
        wait = float(row["wait"])
    return wait

def calculate_new_route(newroute, akeys, distmatrix, starttime, waitmatrix, attractions):
    n = {}
    n["path"] = [newroute[0]]
    n["cost"] = 0
    n["times"] = []
    for a in newroute[1:]:
        n["path"] = n["path"] + [a]
        tofrom = sorted(n["path"][-2:])
        tofromidx = [akeys.index(x) for x in tofrom]
        distcost = distmatrix[tofromidx[0]][tofromidx[1]]
        hour = math.floor((n["cost"]+distcost+starttime)/60)
        waitcost = waitmatrix[akeys.index(a)][hour]
        n["cost"] = n["cost"] + distcost + waitcost + attractions[a]["dur"]
        t = {}
        t["distance"] = distcost
        t["wait"] = waitcost
        t["ride"] = attractions[a]["dur"]
        n["times"].append(t)
    return n

def get_speedrun(parkid, starttime, walkspeed, options):
    # https://en.wikipedia.org/wiki/Branch_and_bound
    # sort queue by heuristic - geeks4geeks article? average of two lowest paths?
    # node data structure: path taken, nodes to go, cost, heuristic

    global cur

    TYPE_FILTER = ["RIDE", "GATE"]

    # Default Options
    optionkeys = options.keys()
    if "method" not in optionkeys:
        options["method"] = "approx" # Assume approximate solution
    if "singlerider" not in optionkeys:
        options["singlerider"] = False # No single rider line unless specified

    # Get a list of all attractions at the park
    attractions = {}
    cur.execute("SELECT * FROM Attractions WHERE parkid = %s AND (type = 'RIDE' OR type = 'GATE') ORDER BY attractionid", parkid)
    for row in cur:
        a = {}
        a["id"] = row["attractionid"]
        a["name"] = row["name"]
        a["slug"] = row["slug"]
        a["type"] = row["type"]
        a["dur"] = float(row["duration"])
        a["lat"] = float(row["lat"])
        a["lon"] = float(row["lon"])
        attractions[row["attractionid"]] = a
    akeys = list(attractions.keys())

    # Create the distance matrix
    distmatrix = np.zeros((len(akeys), len(akeys)))
    #walkspeedmetric = (walkspeed * 1609) / (60*60) # wrong
    walkspeedmetric = walkspeed * 26.8224 # mph to meters per minute
    #print(walkspeedmetric)
    cur.execute("SELECT * FROM Distances")
    for row in cur:
        if row["attraction_a"] in akeys and row["attraction_b"] in akeys:
            a_id = akeys.index(row["attraction_a"])
            b_id = akeys.index(row["attraction_b"])
            distmatrix[a_id][b_id] = round((float(row["distance"]) / walkspeedmetric), 2) # used to have a /60
    #print(distmatrix)

    # Create the wait time matrix
    waitmatrix = np.zeros((len(akeys), 24))
    cur.execute("SELECT AVG(waittime) AS wait, HOUR(queuedt) AS queuehour, attractionid FROM Queue WHERE type = 'STANDBY' AND attractionid IN (SELECT attractionid FROM Attractions WHERE parkid = %s AND (type = 'RIDE' OR type = 'GATE')) GROUP BY queuehour, attractionid ORDER BY attractionid, queuehour", parkid)
    for row in cur:
        ai = akeys.index(row["attractionid"])
        if row["wait"] is not None:
            waitmatrix[ai][row["queuehour"]] = float(row["wait"])
        else:
            # Assume it's a show or a batch load thing
            # Take half the duration, since that's the average time
            # that you'll have to wait for the batch to finish
            waitmatrix[ai][row["queuehour"]] = attractions[row["attractionid"]]["dur"]/2
    # Create the initial node and add to queue
    gate = None
    for a in attractions.values():
        if a["type"] == "GATE":
            gate = a
    if gate is None:
        print("Couldn't find gate")
    #print([a for a in attractions])

    # EXACT SOLUTION (Branch and Bound)
    if options["method"] == "exact":
        rnode = {}
        rnode["path"] = [gate["id"]]
        rnode["todo"] = [a for a in attractions if a not in rnode["path"]]
        rnode["cost"] = 0
        rnode["heur"] = h([akeys.index(a) for a in rnode["todo"]], akeys.index(rnode["path"][-1]), distmatrix)
        rnode["times"] = []
        queue = [rnode]

        # Main loop
        bestendnode = None
        nodecount = 0
        while len(queue) > 0:
            queue = sort_queue(queue)
            # As a metric, get number of combinations left to try
            #print(f"Routes left: {routesleft}")
            nodecount += 1
            if nodecount % 1000 == 0:
                routesleft = 0
                for n in queue:
                    routesleft += math.factorial(len(n["todo"]))
                print(f"Nodes processed: {nodecount}, Queue length: {len(queue)}, Routes left: {routesleft}")
            node = queue.pop(0)
            #print(f'Length {len(node["path"])}\t h {round(node["heur"])}\t c {round(node["cost"])}\t g {round(node["heur"]+node["cost"])}')
            for a in node["todo"]:
                n = {}
                n["path"] = node["path"] + [a]
                #print(n["path"])
                tofrom = sorted(n["path"][-2:])
                tofromidx = [akeys.index(x) for x in tofrom]
                #print(tofrom)
                distcost = distmatrix[tofromidx[0]][tofromidx[1]]
                #print(distcost)
                #waitcost = wait_cost(a, node["cost"]+distcost+starttime)
                hour = math.floor((node["cost"]+distcost+starttime)/60)
                waitcost = waitmatrix[akeys.index(a)][hour]
                n["cost"] = node["cost"] + distcost + waitcost + attractions[a]["dur"]
                n["times"] = node["times"].copy()
                t = {}
                t["distance"] = distcost
                t["wait"] = waitcost
                t["ride"] = attractions[a]["dur"]
                n["times"].append(t)
                n["todo"] = [a for a in attractions if a not in n["path"]]
                n["heur"] = h([akeys.index(a) for a in n["todo"]], akeys.index(n["path"][-1]), distmatrix)
                if bestendnode is not None and n["cost"] + n["heur"] > bestendnode["cost"]:
                    # No way this portion of the tree is better than the given best
                    # Don't even add it to the queue, just move on to the next
                    #r = math.factorial(len(n["todo"]))
                    #if (r > 24):
                        #print(f"Skipped {r} routes")
                    continue
                if len(n["todo"]) == 0:
                    if attractions[n["path"][-1]]["type"] != "GATE":
                        n["todo"] = [gate["id"]]
                        queue.append(n)
                    else:
                        print(f"Tour complete ({len(n['path'])} attractions)")
                        # Tour is complete, check if it's the best
                        if (bestendnode is None) or (n["cost"] < bestendnode["cost"]):
                            print('------------------------------------New best')
                            bestendnode = n
                else:
                    queue.append(n)

        return bestendnode, attractions
    else:
        # APPROXIMATE SOLUTION (2-opt)

        # Start with a nearest neighbor solution
        node = {}
        node["path"] = [gate["id"]]
        node["todo"] = [a for a in attractions if a not in node["path"]]
        node["cost"] = 0
        node["times"] = []
        while len(node["todo"]) != 0:
            nearest = None # None or node
            for a in node["todo"]:
                n = {}
                n["path"] = node["path"] + [a]
                #print(n["path"])
                tofrom = sorted(n["path"][-2:])
                tofromidx = [akeys.index(x) for x in tofrom]
                #print(tofrom)
                distcost = distmatrix[tofromidx[0]][tofromidx[1]]
                #print(distcost)
                #waitcost = wait_cost(a, node["cost"]+distcost+starttime)
                hour = math.floor((node["cost"]+distcost+starttime)/60)
                waitcost = waitmatrix[akeys.index(a)][hour]
                if nearest is None or nearest["cost"] > (node["cost"] + distcost + waitcost + attractions[a]["dur"]):
                    # New nearest neighbor
                    n["cost"] = node["cost"] + distcost + waitcost + attractions[a]["dur"]
                    n["times"] = node["times"].copy()
                    t = {}
                    t["distance"] = distcost
                    t["wait"] = waitcost
                    t["ride"] = attractions[a]["dur"]
                    n["times"].append(t)
                    n["todo"] = [a for a in attractions if a not in n["path"]]
                    nearest = n
            node = nearest
            print(f'Cost: {node["cost"]}\tPath Len: {len(node["path"])}')
        node["path"] = node["path"] + [gate["id"]]
        tofrom = sorted(node["path"][-2:])
        tofromidx = [akeys.index(x) for x in tofrom]
        distcost = distmatrix[tofromidx[0]][tofromidx[1]]
        hour = math.floor((node["cost"]+distcost+starttime)/60)
        waitcost = waitmatrix[akeys.index(a)][hour]
        node["cost"] = node["cost"] + distcost + waitcost + attractions[a]["dur"]
        t = {}
        t["distance"] = distcost
        t["wait"] = waitcost
        t["ride"] = attractions[a]["dur"]
        node["times"].append(t)

        bestpath = node
        newbestpath = node
        while newbestpath is not None:
            newbestpath = None
            # While we haven't found a solution yet or we found something better
            for i in range(1, len(node["path"])-2):
                for k in range(i+1, len(node["path"])-1):
                    #print(f"\ti = {i}, k = {k}")
                    newroute = []
                    routestart = node["path"][0:i]
                    routemid = node["path"][i:k][::-1]
                    routeend = node["path"][k:]
                    if routestart is not None:
                        newroute.extend(routestart)
                    if routemid is not None:
                        newroute.extend(routemid)
                    if routeend is not None:
                        newroute.extend(routeend)
                    n = calculate_new_route(newroute, akeys, distmatrix, starttime, waitmatrix, attractions)
                    if n["cost"] < bestpath["cost"]:
                        if newbestpath is None or n["cost"] < newbestpath["cost"]:
                            print(f"New best path found (cost = {n['cost']}) [2-opt]")
                            newbestpath = n
            if newbestpath is not None:
                bestpath = newbestpath

        # Now try a 3-opt move
        newbestpath = node
        while newbestpath is not None:
            newbestpath = None
            for i in range(2, len(node["path"])-3):
                for j in range(i+1, len(node["path"])-2):
                    for k in range(j+1, len(node["path"])-1):
                        #print(f"i:{i}, j:{j}, k:{k}")
                        # 4 segments: 0 to (i-1), i to (j-1), j to (k-1), k to end
                        newroute = []
                        route_prea = node["path"][0:i-1] # Before A
                        route_a = node["path"][i-1:i+1] # A
                        route_midab = node["path"][i+1:j-1] # Between A and B
                        route_b = node["path"][j-1:j+1] # B
                        route_midbc = node["path"][j+1:k-1] # Between B and C
                        route_c = node["path"][k-1:k+1] # C
                        route_postc = node["path"][k+1:] # After C

                        c0 = route_prea + route_a + route_midab + route_b + route_midbc + route_c + route_postc
                        c1 = route_prea + route_a[::-1] + route_midab + route_b + route_midbc + route_c + route_postc
                        c2 = route_prea + route_a + route_midab + route_b + route_midbc + route_c[::-1] + route_postc
                        c3 = route_prea + route_a + route_midab + route_b[::-1] + route_midbc + route_c + route_postc
                        c4 = route_prea + route_a + route_midab + route_b[::-1] + route_midbc + route_c[::-1] + route_postc
                        c5 = route_prea + route_a[::-1] + route_midab + route_b[::-1] + route_midbc + route_c + route_postc
                        c6 = route_prea + route_a[::-1] + route_midab + route_b + route_midbc + route_c[::-1] + route_postc
                        c7 = route_prea + route_a[::-1] + route_midab + route_b[::-1] + route_midbc + route_c[::-1] + route_postc
                        cases = {0:c0, 1:c1, 2:c2, 3:c3, 4:c4, 5:c5, 6:c6, 7:c7}
                        nodes = {}
                        for c in range(8):
                            nodes[c] = calculate_new_route(cases[c], akeys, distmatrix, starttime, waitmatrix, attractions)
                        bestc = None
                        besttime = None
                        for c in range(8):
                            if nodes[c]["cost"] < bestpath["cost"]:
                                if newbestpath is None or nodes[c]["cost"] < newbestpath["cost"]:
                                    print(f"New best path found (cost = {nodes[c]['cost']}) [3-opt]")
                                    newbestpath = nodes[c]
            if newbestpath is not None:
                print("Setting bestpath")
                bestpath = newbestpath


        return bestpath, attractions

def minutecounttodisp(minutes):
    # Minutes past midnight to pretty time
    # Minutes is likely a float
    hour = math.floor(minutes/60)
    minute = math.floor(minutes%60)
    ampm = "AM"
    if hour == 12:
        ampm = "PM"
    elif hour == 0:
        hour = 12
    elif hour > 12:
        hour = hour - 12
        ampm = "PM"
    return f"{hour}:{str(minute).zfill(2)} {ampm}"

def getnumrides(parkid):
    cur.execute("SELECT COUNT(attractionid) as c FROM Attractions WHERE parkid = %s AND (type = 'RIDE' OR type = 'GATE') ORDER BY attractionid", parkid)
    for row in cur:
        num = row["c"]
    return num

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Finds the best route through a theme park.")
    parser.add_argument('--parkid', default='75ea578a-adc8-4116-a54d-dccb60765ef9', help='ID of the park to speedrun')
    parser.add_argument('--starttime', type=int, default=540, help='Number of minutes after midnight to start')
    parser.add_argument('--walkspeed', type=int, default=4, help='Average walking speed (mph)')

    # Magic Kingdom:        75ea578a-adc8-4116-a54d-dccb60765ef9
    # EPCOT:                47f90d2c-e191-4239-a466-5892ef59a88b
    # Hollywood Studios:    288747d1-8b4f-4a64-867e-ea7c9b27bad8
    # Animal Kingdom:       1c84a229-8862-4648-9c71-378ddd2c7693

    options = {
        "method": "approx",
        "singlerider": False
    }


    args = parser.parse_args()
    bestroute, attractions = get_speedrun(args.parkid, args.starttime, args.walkspeed, options)

    minutes = args.starttime

    print(bestroute)
    print("")
    print("ROUTE:")
    print(f'Start at the main entrance to {attractions[bestroute["path"][0]]["name"]}')
    print(f'\tStart time: {minutecounttodisp(minutes)}')
    for i in range(len(bestroute["path"])-2):
        print(f'{i+1}. Go to {attractions[bestroute["path"][i+1]]["name"]}')
        print(f'\tTime spent walking: {bestroute["times"][i]["distance"]} mins')
        minutes += bestroute["times"][i]["distance"]
        print(f'\t\tArrive at {minutecounttodisp(minutes)}')
        print(f'\tTime spent in line: {bestroute["times"][i]["wait"]} mins')
        minutes += bestroute["times"][i]["wait"]
        print(f'\tTime spent on ride: {bestroute["times"][i]["ride"]} mins')
        minutes += bestroute["times"][i]["ride"]
        print(f'\t\tOff ride at {minutecounttodisp(minutes)}')
    print(f'{len(bestroute["path"])-1}. Go to park exit')
    print(f'\tTime spent walking: {bestroute["times"][-1]["distance"]} mins')
    minutes += bestroute["times"][-1]["distance"]
    print(f'\t\tExit park at {minutecounttodisp(minutes)}')
