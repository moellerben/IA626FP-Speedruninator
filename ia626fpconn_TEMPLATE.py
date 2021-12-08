def getConnInfo():
    MYSQL_CONN = {}
    MYSQL_CONN["HOST"] = 'MYSQL_SERVER_ADDRESS'
    MYSQL_CONN["PORT"] = 1234 # MYSQL_SERVER_PORT
    MYSQL_CONN["USER"] = 'MYSQL_USERNAME'
    MYSQL_CONN["PASS"] = 'MYSQL_PASSWORD'
    MYSQL_CONN["DB"] = 'moellebr_IA626FP'
    return MYSQL_CONN

def getDirectionsAPIKey():
    return "YOUR_GOOGLE_DIRECTIONS_API_KEY" # Not needed to run project
