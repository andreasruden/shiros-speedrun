import functools
import glob
import json
import os
import re
import sys

FACTION_ALLIANCE = 0x2
FACTION_HORDE = 0x4
RACE_NIGHT_ELF = 0x8

warned_quests = []
questsDB = {}
wroteOverflow = False
routeCWD = ''
outputCWD = ''

def error(line, msg, fatal=False):
    if fatal:
        print('  ERRROR at line %s: %s!' % (line, msg))
    else:
        print('  Warning at line %d: %s.' % (line, msg))
    if fatal:
        sys.exit(0)

def warning(line, questid, msg):
    if questid in warned_quests:
        return
    print('  Warning for quest %s at line %d: %s.' % (questid, line, msg))
    warned_quests.append(questid)

def is_preceeded_by(line, n, text):
    numwords = len(text.split())
    
    while True:
        ws = 0
        s = ''
        i = line.find('[Q', n-1)
        while line[i] in [' ', '[']:
            i -= 1
        in_word = False
        while ws < numwords and i >=0 and line[i] != ']':
            s = line[i] + s
            if line[i] == ' ':
                in_word = False
                ws += 1
            else:
                in_word = True
            i -= 1
        if in_word:
            ws += 1
        if ws == numwords and s.strip().lower().rfind(text.lower()) > -1:
            return True
        elif ws == 1 and s.strip() == ',' or s.strip().lower() == 'and':
            n = line.rfind(' [Q', 0, n)
            if n == -1:
                return False
        else:
            return False

def process_line(line, route, linenum):
    n = 0
    while True:
        check_hearthstone(line, route, linenum)
        try:
            (quest, n, start) = find_next_quest_with_start(line, n)
        except:
            error(linenum, 'Invalid quest formatting', True)
        if quest == None:
            return
        if quest.op not in ['A', 'C', 'T']:
            error(linenum, 'Invalid operation for quest `Q%s`' % quest.op, True)
        
        if is_preceeded_by(line, start, 'Accept') and quest.op != 'A':
            warning(linenum, quest.id, 'Opcode is `%s` but instruction says `Accept`' % quest.op)
        elif is_preceeded_by(line, start, 'Complete') and quest.op != 'C':
            warning(linenum, quest.id, 'Opcode is `%s` but instruction says `Complete`' % quest.op)
        elif is_preceeded_by(line, start, 'Turn in') and quest.op != 'T':
            warning(linenum, quest.id, 'Opcode is `%s` but instruction says `Turn in`' % quest.op)
    
        if quest.op == 'A' and quest.id in route.accepted:
            warning(linenum, quest.id, 'Has already been accepted')
        elif quest.op != 'T' and quest.id in route.completed:
            warning(linenum, quest.id, 'Has already been completed')
        elif quest.id in route.finished and not '!OptionalFinish' in line:
            warning(linenum, quest.id, 'Has already been turned in')

        if quest.op == 'A':
            if quest.id not in route.accepted:
                route.accepted.append(quest.id)
            # Check for questlog overflow
            numquests = len(route.accepted) + len(route.completed)
            if numquests > 25:
                global wroteOverflow
                if wroteOverflow:
                    warning(linenum, quest.id, 'Accepting this quest overflows our questlog. We are now at %d quests' % numquests)
                else:
                    warning(linenum, quest.id, 'Accepting this quest overflows our questlog. We are now at %d quests. Wrote questlog to overflow.txt' % numquests)
                    write_questlog('overflow.txt', route)
                    wroteOverflow = True
        elif quest.op == 'C' and ',' not in quest.id:
            if quest.id not in route.accepted:
                warning(linenum, quest.id, 'Has not been accepted')
            else:
                route.accepted.remove(quest.id)
            route.completed.append(quest.id)
        elif quest.op == 'T':
            if quest.id not in route.accepted and quest.id not in route.completed:
                if '!FinishWithoutAccept' not in line and '!OptionalFinish' not in line:
                    warning(linenum, quest.id, 'Trying to turn in quest not in our quest log')
            if quest.id in route.accepted:
                route.accepted.remove(quest.id)
            if quest.id in route.completed:
                route.completed.remove(quest.id)
            route.finished.append(quest.id)
        
        if ',' not in quest.id:
            realQuestInfo = questsDB[quest.id]
            if realQuestInfo['name'] != quest.name:
                warning(linenum, quest.id, 'Incorrectly named (%s). Should be: "%s"' % (quest.name, realQuestInfo['name']))

def find_next_quest_with_start(line, n=0):
    instr = ''
    space = False
    while n < len(line):
        char = line[n]
        if char == '-' and line[n+1] == '-':
            return (None, len(line), -1)
        elif char == ' ':
            space = True
            n += 1
        elif char == '[' and line[n+1] == 'Q':
            start = n - 1
            quest, n = find_next_quest(line, n)
            return (quest, n, start)
        else:
            if space:
                space = False
                instr = ''
            instr += char
            n += 1
    return (None, len(line), -1)

def find_next_quest(line, n=0):
    # Read until '['
    found = False
    for char in line[n:]:
        n += 1
        if char == '[':
            found = True
            break
    if not found:
        return (None, len(line))
    
    quest = Quest() # {'id':'', 'op':'none', 'name':''}

    # Read opcode
    assert(line[n] == 'Q')
    quest.op = line[n+1]
    n += 2

    # Read quest id
    quest.id = ''
    while line[n] != ' ':
        quest.id = quest.id + line[n]
        n += 1
    n += 1 # skip space

    quest.name = ''
    while line[n] != ']':
        quest.name += line[n]
        n += 1

    return (quest, n+1)

def process_file(file, route):
    print('%s...' % file)
    with open(file) as filehandle:
        linenum = 0
        started = False
        for line in filehandle:
            linenum += 1
            # Skip until route instructions start
            if not started and not line.startswith('[['):
                continue
            started = True
            # Skip route-instruction lines
            if line.startswith('['):
                continue
            # Skip empty lines
            if len(line.strip()) == 0:
                continue
            # Skip lines that are only comments
            if line.lstrip().startswith('--'):
                continue
            # Skip end-of-route line
            if line.startswith(']]'):
                break
            process_line(line.rstrip(), route, linenum)
    print()

def check_hearthstone(line, route, linenum):
    # Set Hearthstone
    match = re.search(r'\[S (.*)\]', line)
    if match:
        route.hearthstone = match.group(1)
    # Use Hearthstone
    match = re.search(r'\[H (.*)\]', line)
    if match:
        if route.hearthstone != match.group(1):
            msg = 'Trying to use hearthstone to go to %s, but it is bound to %s' % (match.group(1), route.hearthstone)
            error(linenum, msg)

def scan_files():
    route = Route() # {'accepted':[], 'completed':[], 'finished':[]}
    files = []
    for file in glob.glob('*.lua'):
        wds = file.split()
        if len(wds) == 0 or not wds[0].isdigit():
            continue
        files.append(file)
    files = sorted(files)
    for file in files:
        process_file(file, route)
        os.chdir(outputCWD)
        with open('questlog_data.txt', 'a') as f:
            f.write('%s:\n' % file)
        os.chdir(routeCWD)
        write_questlog('questlog_data.txt', route)
    return route

def dump_incomplete_quests(route, maxlevel):
    incomplete = {}
    incomplete_unknown = []
    for id in questsDB:
        quest = questsDB[id]
        if id in route.finished:
            continue
        if quest['reqlevel'] > maxlevel:
            continue
        if 'accepthostilemask' in quest and quest['accepthostilemask'] & FACTION_ALLIANCE != 0:
            continue
        if quest['races'] != 0 and quest['races'] & RACE_NIGHT_ELF == 0:
            continue
        if 'acceptzone' not in quest or quest['acceptzone'] == 'Unknown':
            incomplete_unknown.append(quest)
        else:
            if quest['acceptzone'] not in incomplete:
                incomplete[quest['acceptzone']] = []
            incomplete[quest['acceptzone']].append(quest)
    with open('incomplete_quests.txt', 'w') as f:
        for zone in incomplete:
            f.write('%s:\n' % zone)
            for quest in incomplete[zone]:
                if quest['classes'] == 0:
                    f.write('  [%d] %s (%d) (z=%s)    -> %s\n' % (quest['level'], quest['name'], quest['id'], quest['zone'], ('https://tbc.wowhead.com/quest=%s' % quest['id'])))
                else:
                    f.write('  CLASS-SPECIFIC [%d] %s (%d) (z=%s)    -> %s\n' % (quest['level'], quest['name'], quest['id'], quest['zone'], ('https://tbc.wowhead.com/quest=%s' % quest['id'])))
            f.write('\n')
        f.write('\n\n\n\nUnknown:\n')
        for quest in incomplete_unknown:
            if quest['classes'] == 0:
                f.write('  [%d] %s (%d) (z=%s)    -> %s\n' % (quest['level'], quest['name'], quest['id'], quest['zone'], ('https://tbc.wowhead.com/quest=%s' % quest['id'])))
            else:
                f.write('  CLASS-SPECIFIC [%d] %s (%d) (z=%s)    -> %s\n' % (quest['level'], quest['name'], quest['id'], quest['zone'], ('https://tbc.wowhead.com/quest=%s' % quest['id'])))
        print('Wrote a list of all incompleted quests with req<=58 to incomplete_quests.txt!')

def write_questlog(filename, route):
    rawquests = route.accepted + route.completed

    questlog = {}
    for id in rawquests:
        quest = questsDB[id]
        if quest['zone'] not in questlog:
            questlog[quest['zone']] = []
        questlog[quest['zone']].append(quest)
    
    # Sorting: Categories are sorted alphabetically. Quests are sorted first by level, then alphabetically.
    for zone in questlog:
        questlog[zone].sort(key=lambda q: (q['level'], q['name']))

    os.chdir(outputCWD)
    with open(filename, 'a') as f:
        f.write('%d quests:' % len(rawquests))
        for zone in questlog:
            f.write('\\\\*%s:* ' % zone)
            for i in range(0, len(questlog[zone])):
                quest = questlog[zone][i]
                f.write('[%d] %s (%s)%s' % (quest['level'], quest['name'], quest['id'], ', ' if i+1 < len(questlog[zone]) else ''))
        f.write('\n\n')
    os.chdir(routeCWD)

class Route:
    def __init__(self):
        self.accepted = []
        self.completed = []
        self.finished = []
class Quest:
    pass

def main():
    if len(sys.argv) < 2:
        print('Usage %s path-to-route' % sys.argv[0])
        return
    
    global questsDB
    with open('quests.json', 'r') as f:
        questsDB = json.load(f)
    
    if os.path.isfile('questlog_data.txt'):
        os.remove('questlog_data.txt')
    with open('questlog_data.txt', 'w') as f:
        f.write('The questlog has been dumped *after* completion of a file:\n\n')

    global outputCWD, routeCWD
    outputCWD = os.getcwd()
    routeCWD = sys.argv[1]
    os.chdir(routeCWD)
    route = scan_files()
    os.chdir(outputCWD)
    dump_incomplete_quests(route, 58)

    print('Dumped state of questlog between files into questlog_data.txt')

if __name__ == '__main__':
    main()
