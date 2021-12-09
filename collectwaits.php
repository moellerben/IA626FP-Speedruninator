<?php

# Collects wait times from all parks that are being kept track of

require("connection.php"); # Not provided in repo
# This connection file just needs to initialize a MySQLi object named $mysqli
# which is connected to your database of choice

$API_ROOT = "https://api.themeparks.wiki/v1";

function slugify($text, string $divider = "") {
    // replace non letter or digits by divider
    $text = preg_replace('~[^\pL\d]+~u', $divider, $text);
    // transliterate
    $text = iconv('utf-8', 'us-ascii//TRANSLIT', $text);
    // remove unwanted characters
    $text = preg_replace('~[^-\w]+~', '', $text);
    // trim
    $text = trim($text, $divider);
    // remove duplicate divider
    $text = preg_replace('~-+~', $divider, $text);
    // lowercase
    $text = strtolower($text);
    if (empty($text)) {
        return 'n-a';
    }
    return $text;
}

# Step 1: Get list of tracked parks
$park_ids = [];
$res = $mysqli->query("SELECT * FROM Parks WHERE `parentid` IS NOT NULL");
while ($row = $res->fetch_assoc()) {
    $park_ids[] = $row['parkid'];
}

# Check if we already have a schedule for each of the parks
$haveschedules = [];
$today = date("Y-m-d");
$res = $mysqli->query("SELECT `parkid` FROM `ParkHours` WHERE `hoursdate` >= '$today'");
while ($row = $res->fetch_assoc()) {
    $haveschedules[] = $row['parkid'];
}

# Get schedules for each of the parks
$dates = [];
$dt = new DateTime("now");
$dates[] = $dt->format("Y-m-d");
for ($i=1; $i < 7; $i++) {
    $dt = new DateTime("now");
    $dt->add(new DateInterval("P$i" . "D"));
    $dates[] = $dt->format("Y-m-d");
}

$schedules = [];
foreach ($park_ids as $park_id) {
    if (!in_array($park_id, $haveschedules)) {
        # Need to grab the schedule from the API
        $schedule_url = $API_ROOT."/entity/".$park_id."/schedule";
        $schedule_json = json_decode(file_get_contents($schedule_url));
        # Toss the schedule in the database for the next week
        foreach ($schedule_json->schedule as $openblock) {
            if (in_array($openblock->date, $dates)) {
                $schedblock = [];
                $schedblock["hoursdate"] = $openblock->date;
                $schedblock["type"] = $openblock->type;
                $schedblock["description"] = $openblock->description;
                $schedblock["parkid"] = $park_id;
                $opendtz = date_create_from_format('Y-m-d?H:i:sP', $openblock->openingTime); # 2021-10-08T20:00:00-04:00
                $schedblock["opendt"] = $opendtz->format('Y-m-d H:i:s');
                $closedtz = date_create_from_format('Y-m-d?H:i:sP', $openblock->closingTime);
                $schedblock["closedt"] = $closedtz->format('Y-m-d H:i:s');
                $schedules[] = $schedblock;
            }
        }
    }
}

if (count($schedules) == 0) {
    print("No schedules to add<br />");
} else {
    $enter_schedules_sql = "INSERT INTO ParkHours (`hoursdate`, `type`, `description`, `opendt`, `closedt`, `parkid`) VALUES";
    $sched_entries = [];
    foreach($schedules as $sched) {
        $sched_entry = "('%s', '%s', '%s', '%s', '%s', '%s')";
        $sched_entries[] = sprintf($sched_entry, $sched["hoursdate"], $sched["type"], $sched["description"], $sched["opendt"], $sched["closedt"], $sched["parkid"]);
    }
    $enter_schedules_sql .= implode(", ", $sched_entries);
    $enter_schedules_sql .= ";";
    $mysqli->query($enter_schedules_sql);

    print("Added schedules (allgedley)<br />");
    print($enter_schedules_sql);
}

# Get wait times on all rides that are open
/*
{
      "id": "34c4916b-989b-4ff1-a7e3-a6a846a3484f",
      "name": "Millennium Falcon: Smugglers Run",
      "entityType": "ATTRACTION",
      "parkId": "288747d1-8b4f-4a64-867e-ea7c9b27bad8",
      "externalId": "19263735;entityType=Attraction",
      "queue": {
        "STANDBY": {
          "waitTime": 40
        },
        "SINGLE_RIDER": {
          "waitTime": null
        }
      },
      "status": "OPERATING",
      */
# Get a list of all attractions in our database
$attractionids = [];
$res = $mysqli->query("SELECT `attractionid` FROM `Attractions`");
while ($aid = $res->fetch_assoc()) {
    $attractionids[] = $aid['attractionid'];
}
print("Already have ".count($attractionids)." attractions tracked<br />");

# Reduce API calls by getting all info from root destinations
$waits = [];
$curdt = date("Y-m-d H:i:s");
$res = $mysqli->query("SELECT `parkid` FROM `Parks` WHERE `parentid` IS NULL");
while ($dest = $res->fetch_assoc()) {
    $live_url = $API_ROOT . "/entity/" . $dest['parkid'] . "/live";
    $live_json = json_decode(file_get_contents($live_url));
    foreach($live_json->liveData as $livedata) {
        if ($livedata->entityType != "ATTRACTION") {
            # Only keep track of attractions
            continue;
        }
        if ($livedata->queue == NULL) {
            # Don't grab attractions with no queue
            continue;
        }
        if (($livedata->status == "CLOSED") || ($livedata->status == "REFURBISHMENT")) {
            # Don't write down queue times for closed attractions
            # Keep track of downtime though
            continue;
        }
        # Do we already have this attraction tracked, or is it a new ride?
        if (!in_array($livedata->id, $attractionids)) {
            # We don't have it, grab from API and store in DB
            print("Need to grab info on ".$livedata->name." (id ".$livedata->id.")<br />");
            $attrinfo_url = $API_ROOT . "/entity/" . $livedata->id;
            #print("Getting info from ".$attrinfo_url."<br />");
            $attrinfo_json = json_decode(file_get_contents($attrinfo_url));
            $slug = slugify($attrinfo_json->name);
            $attrinsertquery = "INSERT INTO `Attractions` ";
            $attrinsertquery .= "(`attractionid`, `name`, `slug`, `type`, `lat`, `lon`, `parkid`) ";
            $attrinsertquery .= "VALUES ";
            $aiqsprintf = "('%s', '%s', '%s', '%s', '%s', '%s', '%s');";
            $attrinsertquery .= sprintf($aiqsprintf, $attrinfo_json->id,
                $mysqli->real_escape_string($attrinfo_json->name), $slug,
                $attrinfo_json->attractionType, $attrinfo_json->location->latitude,
                $attrinfo_json->location->longitude, $attrinfo_json->parentId);
            #print($attrinsertquery);
            #print("<br />");
            $mysqli->query($attrinsertquery);
        }
        #var_dump($livedata->queue);
        #print("<br />");
        # Only queues we're looking at are standby and single rider
        if ($livedata->queue->STANDBY != NULL) {
            $wait = [];
            $wait['type'] = "STANDBY";
            $wait['queuedt'] = $curdt;
            $wait['waittime'] = $livedata->queue->STANDBY->waitTime;
            $wait['status'] = $livedata->status;
            $wait['lastupdate'] = date_format(date_timezone_set(date_create_from_format('Y-m-d?H:i:s?', $livedata->lastUpdated, timezone_open("UTC")), timezone_open(date_default_timezone_get())), 'Y-m-d H:i:s');
            $wait['attractionid'] = $livedata->id;
            $waits[] = $wait;
        }
        if ($livedata->queue->SINGLE_RIDER != NULL) {
            $wait = [];
            $wait['type'] = "SINGLE_RIDER";
            $wait['queuedt'] = $curdt;
            $wait['waittime'] = $livedata->queue->SINGLE_RIDER->waitTime;
            $wait['status'] = $livedata->status;
            $wait['lastupdate'] = date_format(date_timezone_set(date_create_from_format('Y-m-d?H:i:s?', $livedata->lastUpdated, timezone_open("UTC")), timezone_open(date_default_timezone_get())), 'Y-m-d H:i:s');
            $wait['attractionid'] = $livedata->id;
            $waits[] = $wait;
        }
        #print("<br />");
    }
}
# Now we have all the waits, add them to the database
$waitins = "INSERT INTO `Queue` (`queuedt`, `waittime`, `type`, `status`, `lastupdate`, `attractionid`) VALUES ";
$wait_entries = [];
foreach($waits as $wait) {
    if ($wait["waittime"] == NULL) {
        $wait["waittime"] = "NULL";
    } else {
        $wait["waittime"] = "'".$wait["waittime"]."'";
    }
    $wait_entry = "('%s', %s, '%s', '%s', '%s', '%s')";
    $wait_entries[] = sprintf($wait_entry, $wait["queuedt"], $wait["waittime"],
        $wait["type"], $wait["status"], $wait["lastupdate"], $wait["attractionid"]);
}
$waitins .= implode(", ", $wait_entries);
$waitins .= ";";
#print($waitins."<br /><br />");
$mysqli->query($waitins);
print("Inserted ".count($waits)." queue times");

?>
