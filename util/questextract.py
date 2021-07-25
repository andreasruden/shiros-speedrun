import getpass
import json
import MySQLdb
import MySQLdb.cursors
import sys

areatable = {} # area/zone id -> area/zone name

class Quest:
    pass

def find_questgiver(row, cur):
    # X_questrelation -> X starts quest; X_questinvolved -> X ends quest
    cur.execute('SELECT id FROM creature_questrelation WHERE quest=%s', (row['entry'],))
    if cur.rowcount == 1:
        npcid = cur.fetchone()['id']
        cur.execute('SELECT faction_A FROM creature_template where entry=%s', (npcid,))
        faction = cur.fetchone()['faction_A'] # faction_A and faction_H are the same
        cur.execute('SELECT map, position_x, position_y, position_z FROM creature WHERE id=%s', (npcid,))
        if cur.rowcount > 0:
            crow = cur.fetchone()
            return (npcid, faction, crow['map'], crow['position_x'], crow['position_y'], crow['position_z'])
        else:
            return (npcid, 0, -1, -1, -1, -1)
    
    cur.execute('SELECT id FROM gameobject_questrelation WHERE quest=%s', (row['entry'],))
    if cur.rowcount == 1:
        goid = cur.fetchone()['id']
        cur.execute('SELECT map, position_x, position_y, position_z FROM gameobject WHERE id=%s', (goid,))
        if cur.rowcount > 0:
            orow = cur.fetchone()
            return (-goid, 0, orow['map'], orow['position_x'], orow['position_y'], orow['position_z'])
        else:
            return (-goid, 0, -1, -1, -1, -1)
    
    return (0, 0, -1, -1, -1, -1)

def patch_zoneorsort(quest):
    special = {-261:'Hunter', -262:'Priest', -162:'Rogue', -141:'Paladin', -81:'Warrior', -161:'Mage', -61:'Warlock', -263:'Druid', -82:'Shaman', -284:'Special', -101:'Fishing', -304:'Cooking', -324:'First Aid', -264:'Tailoring', -181:'Alchemy', -201:'Engineering', -24:'Herbalism', -182:'Leatherworking', -121:'Blacksmithing', -221:'Treasure Map', -25:'Battlegrounds', -22:'Seasonal', -364:'Darkmoon Faire', -1:'Epic', -365:'Ahn\'Qiraj War', -366:'Lunar Festival', -368:'Invasion', -367:'Reputation', -369:'Midsummer', -370:'Brewfest', 0:'Unused', -344:'Unused'}
    if quest.zoneorsort in areatable:
        quest.zone = areatable[quest.zoneorsort]
    elif quest.zoneorsort in special:
        quest.zone = special[quest.zoneorsort]
    else:
        print('%d has non-existant zoneorsort %d' % (quest.id, quest.zoneorsort))
    delattr(quest, 'zoneorsort')

def build_quest_db(conn):
    quests = {}
    cur = conn.cursor()
    cur2 = conn.cursor()
    cur.execute('SELECT * FROM quest_template')
    n = cur.rowcount
    i = 0
    for row in cur:
        i += 1
        if i % 500 == 0:
            print('%d/%d' % (i, n))
        quest = Quest()
        quest.id = row['entry']
        quest.name = row['Title']
        quest.reqlevel = row['MinLevel']
        quest.level = row['QuestLevel']
        quest.races = row['RequiredRaces']
        quest.classes = row['RequiredClasses']
        quest.skill = row['RequiredSkill']
        quest.skillvalue = row['RequiredSkillValue']
        quest.prevquestid = row['PrevQuestId']
        quest.nextquestid = row['NextQuestId']
        quest.exclusivegroup = row['ExclusiveGroup']
        quest.nextquestinchain = row['NextQuestInChain']
        quest.suggestedplayers = row['SuggestedPlayers']
        quest.zoneorsort = row['ZoneOrSort']
        patch_zoneorsort(quest)
        (nid, faction, map, x, y, z) = find_questgiver(row, cur2)
        quest.acceptid = int(nid)
        quest.acceptfaction = faction
        quest.acceptmap = int(map)
        quest.x = float(x)
        quest.y = float(y)
        quest.z = float(z)
        quests[quest.id] = quest
    return quests

def patch_areas(quests):
    # Read patch file if it exists
    answers = {}
    try:
        with open('areaanswers.txt', 'r') as f:
            for answer in f:
                id, hostilemask, zone = answer.split(' ', 2)
                answers[int(id)] = (int(hostilemask), zone.strip())
    except OSError:
        # Write file with map, x, y, z
        writtenids = set()
        with open('areaqueries.txt', 'w') as f:
            for key in quests:
                quest = quests[key]
                if quest.acceptid == 0 or quest.acceptid in writtenids:
                    continue
                f.write('%d %d %d %f %f %f\n' % (quest.acceptid, quest.acceptfaction, quest.acceptmap, quest.x, quest.y, quest.z))
                writtenids.add(quest.acceptid)
        return
    # Add the zones
    for key in quests:
        quest = quests[key]
        if quest.acceptid == 0:
            continue
        hostilemask, zone = answers[quest.acceptid]
        quest.accepthostilemask = hostilemask
        quest.acceptzone = zone

def write_to_json(quests):
    with open('quests.json', 'w') as f:
        json.dump(quests, f, indent=4, default=lambda quest: quest.__dict__)

def read_area_table():
    with open('areatable.txt') as f:
        for row in f:
            id, name = row.split(' ', 1)
            areatable[int(id)] = name.strip()

def main():
    if len(sys.argv) != 4:
        print('Usage: %s host user database' % sys.argv[0])
        return
    
    pwd = getpass.getpass()

    conn = MySQLdb.connect(host=sys.argv[1], user=sys.argv[2], password=pwd, database=sys.argv[3], cursorclass=MySQLdb.cursors.DictCursor)
    read_area_table()
    db = build_quest_db(conn)
    conn.close()
    patch_areas(db)

    write_to_json(db)

if __name__ == '__main__':
    main()
