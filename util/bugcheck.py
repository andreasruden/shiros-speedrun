import glob
import sys

def process_line(line, route, linenum):
    n = 0
    while True:
        try:
            (quest, n, instr) = find_next_quest_with_instruction(line, n)
        except:
            print('ERROR: Invalid quest formatting at line %d.' % linenum)
            sys.exit(-1)
        if quest == None:
            return
        # print(instr, quest)

def find_next_quest_with_instruction(line, n=0):
    instr = ''
    space = False
    while n < len(line):
        char = line[n]
        if char == '-' and line[n+1] == '-':
            return (None, len(line), 'None')
        elif char == ' ':
            space = True
            n += 1
        elif char == '[' and line[n+1] == 'Q':
            quest, n = find_next_quest(line, n)
            return (quest, n, instr)
        else:
            if space:
                space = False
                instr = ''
            instr += char
            n += 1
    return (None, len(line), 'None')

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
    
    quest = {'id':0, 'op':'none', 'name':''}

    # Read opcode
    assert(line[n] == 'Q')
    quest['op'] = line[n+1]
    n += 2

    # Read quest id
    id = ''
    while line[n].isdigit():
        id = id + line[n]
        n += 1
    quest['id'] = int(id)
    n += 1 # skip space

    while line[n] != ']':
        quest['name'] += line[n]
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

def scan_files():
    route = {'accepted':[], 'completed':[], 'finished':[]}
    files = []
    for file in glob.glob('*.lua'):
        wds = file.split()
        if len(wds) == 0 or not wds[0].isdigit():
            continue
        files.append(file)
    files = sorted(files)
    for file in files:
        process_file(file, route)

def main():
    scan_files()

if __name__ == '__main__':
    main()
