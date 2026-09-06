import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TEXTS=[
"Tom Cruise, photographed in nineteen eighty-nine and twenty twenty-five. Thirty-six years apart. Top Gun and Mission Impossible helped define a career built around big-screen adventure.",
"Leonardo DiCaprio, in two thousand and twenty twenty-five. A quarter century separates these portraits. From Titanic to Inception, his screen career has moved between romance, suspense and spectacle.",
"Tom Hanks, in nineteen eighty-nine and twenty twenty-four. Thirty-five years between photographs. From Big to Forrest Gump, he has brought warmth, humor and dramatic weight to unforgettable characters.",
"Brad Pitt, in two thousand one and twenty twenty-four. Twenty-three years apart. Fight Club and Ocean's Eleven show two very different sides of his long screen career.",
"Keanu Reeves, in two thousand six and twenty twenty-five. Nineteen years between photographs. From The Matrix to John Wick, his quiet screen presence has powered some very memorable action.",
"Johnny Depp, in nineteen ninety-two and twenty twenty-three. Thirty-one years apart. Edward Scissorhands and Captain Jack Sparrow reveal a career shaped by distinctive costumes, characters and transformations.",
"Denzel Washington, in nineteen ninety and twenty twenty-five. Thirty-five years between these appearances. Glory, Malcolm X and Training Day are landmarks in a career known for commanding performances.",
"George Clooney, in nineteen ninety-five and twenty twenty-five. Three decades between portraits. Ocean's Eleven and The Descendants show the charm and dramatic range behind his familiar leading-man image.",
"Matt Damon, in two thousand one and twenty twenty-four. Twenty-three years apart. From Good Will Hunting to the Bourne films, intelligence and determination have shaped many of his characters.",
"Ben Affleck, in nineteen ninety-eight and twenty twenty-three. A twenty-five-year comparison. Good Will Hunting and Argo mark different chapters in a career spent both acting and directing.",
"Will Smith, in nineteen ninety-three and twenty twenty-five. Thirty-two years apart. From The Fresh Prince to Men in Black, his career connects television, movies and music.",
"Robert Downey Junior, in nineteen ninety and twenty twenty-six. Thirty-six years separate these portraits. Iron Man and Sherlock Holmes made his quick wit and expressive performances familiar to worldwide audiences.",
"Harrison Ford, in two thousand seven and twenty twenty-five. Eighteen years apart. From Han Solo to Indiana Jones, his characters have become enduring symbols of big-screen adventure.",
"Morgan Freeman, in nineteen ninety and twenty twenty-three. Thirty-three years between portraits. The Shawshank Redemption and Million Dollar Baby are just two chapters in a remarkable screen career.",
"Robert De Niro, in nineteen eighty-eight and twenty twenty-five. Thirty-seven years apart. Taxi Driver and Raging Bull helped establish the intense, character-driven performances associated with his name.",
"Al Pacino, in nineteen ninety-six and twenty twenty-six. Three decades between photographs. The Godfather and Scarface remain signature roles in a career filled with forceful, memorable characters.",
"Michael Douglas, in nineteen eighty-four and twenty twenty-five. Forty-one years apart. Wall Street and The American President show contrasting sides of a screen career stretching across decades.",
"Jeff Bridges, in two thousand and twenty twenty-five. A quarter century between portraits. From Tron to The Big Lebowski, he has brought an easygoing presence to very different worlds.",
"Kevin Bacon, in two thousand four and twenty twenty-five. Twenty-one years apart. Footloose and Apollo Thirteen capture different parts of a career ranging from music-driven stories to drama.",
"Samuel L Jackson, in two thousand eight and twenty twenty-four. Sixteen years between photographs. From Pulp Fiction to Nick Fury, his screen presence connects independent cinema and blockbuster franchises.",
"Arnold Schwarzenegger, in nineteen eighty-four and twenty twenty-five. Forty-one years apart. The Terminator and Predator helped turn a bodybuilding champion into one of Hollywood's most recognizable action stars.",
"Sylvester Stallone, in nineteen eighty-five and twenty twenty-five. Forty years between photographs. Rocky and Rambo became defining characters for a performer whose career mixes action, determination and underdog stories.",
"Nicolas Cage, in two thousand seven and twenty twenty-four. Seventeen years apart. From Leaving Las Vegas to National Treasure, his filmography moves between intimate drama and large-scale adventure.",
"Hugh Jackman, in two thousand three and twenty twenty-five. Twenty-two years between photographs. Wolverine and The Greatest Showman highlight his range across superhero spectacle, singing and stage-inspired storytelling.",
"Christian Bale, in nineteen eighty-eight and twenty twenty-two. Thirty-four years apart. From Empire of the Sun to Batman, his career began young and grew into famously transformative performances.",
"Ryan Reynolds, in two thousand seven and twenty twenty-five. Eighteen years between portraits. From romantic comedy to Deadpool, quick timing and self-aware humor became central to his screen persona.",
"Ryan Gosling, in two thousand seven and twenty twenty-three. Sixteen years apart. The Notebook, La La Land and Barbie trace a career moving between romance, music and playful comedy.",
"Jake Gyllenhaal, in two thousand five and twenty twenty-five. Twenty years between photographs. Donnie Darko, Brokeback Mountain and Nightcrawler show the variety of characters he has brought to the screen.",
"Matthew McConaughey, in two thousand four and twenty twenty-five. Twenty-one years apart. From Dazed and Confused to Interstellar, his career moved far beyond a single kind of leading-man role.",
"Ewan McGregor, in two thousand one and twenty twenty-four. Twenty-three years between photographs. Trainspotting, Moulin Rouge and Obi-Wan Kenobi connect independent film, musical romance and a galaxy far away."
]
FILMS=[
['Top Gun','Mission: Impossible'],['Titanic','Inception'],['Big','Forrest Gump'],['Fight Club',"Ocean's Eleven"],['The Matrix','John Wick'],['Edward Scissorhands','Jack Sparrow'],['Glory','Malcolm X','Training Day'],["Ocean's Eleven",'The Descendants'],['Good Will Hunting','Bourne'],['Good Will Hunting','Argo'],['The Fresh Prince of Bel-Air','Men in Black'],['Iron Man','Sherlock Holmes'],['Han Solo','Indiana Jones'],['The Shawshank Redemption','Million Dollar Baby'],['Taxi Driver','Raging Bull'],['The Godfather','Scarface'],['Wall Street','The American President'],['Tron','The Big Lebowski'],['Footloose','Apollo 13'],['Pulp Fiction','Nick Fury'],['The Terminator','Predator'],['Rocky','Rambo'],['Leaving Las Vegas','National Treasure'],['Wolverine','The Greatest Showman'],['Empire of the Sun','Batman'],['Deadpool','romantic comedy'],['The Notebook','La La Land','Barbie'],['Donnie Darko','Brokeback Mountain','Nightcrawler'],['Dazed and Confused','Interstellar'],['Trainspotting','Moulin Rouge','Obi-Wan Kenobi']]
INTRO="Thirty Hollywood stars. Sixty photographs. Decades of movie memories. See how familiar faces change across time. Then, and now."
OUTRO="Thirty careers. Countless movie memories. Which comparison surprised you most, and which star should we feature next?"
CHAPTERS=['FAMILIAR FACES','SIGNATURE LEADING MEN','SCREEN ORIGINALS','DECADES ON SCREEN','ACTION & TRANSFORMATION','THE NEXT CHAPTER']
actors=json.loads((ROOT/'actors.json').read_text())
# Compact visual subtitles use numeric years; the speech scripts spell them out.
number_words={1984:'nineteen eighty-four',1985:'nineteen eighty-five',1988:'nineteen eighty-eight',1989:'nineteen eighty-nine',1990:'nineteen ninety',1992:'nineteen ninety-two',1993:'nineteen ninety-three',1995:'nineteen ninety-five',1996:'nineteen ninety-six',1998:'nineteen ninety-eight',2000:'two thousand',2001:'two thousand one',2003:'two thousand three',2004:'two thousand four',2005:'two thousand five',2006:'two thousand six',2007:'two thousand seven',2008:'two thousand eight',2022:'twenty twenty-two',2023:'twenty twenty-three',2024:'twenty twenty-four',2025:'twenty twenty-five',2026:'twenty twenty-six'}
def caption(text):
    for n,s in sorted(number_words.items(),key=lambda x:-len(x[1])):text=text.replace(s,str(n))
    text=text.replace('Robert Downey Junior','Robert Downey Jr.').replace('Samuel L Jackson','Samuel L. Jackson').replace('Apollo Thirteen','Apollo 13').replace('Mission Impossible','Mission: Impossible')
    return text
parts=[dict(id='intro',text=INTRO,caption=INTRO,start=0.,duration=10.)]
for i,(a,text,films) in enumerate(zip(actors,TEXTS,FILMS)):
    parts.append(dict(id=f'actor_{i:02d}',actor=i,name=a['name'],text=text,caption=caption(text),start=10+i*15.,duration=15.,films=films,chapter=CHAPTERS[i//5]))
parts.append(dict(id='outro',text=OUTRO,caption=OUTRO,start=460.,duration=10.))
# Eight generation calls, comfortably within the tool's 1,500-character limit.
batches=[]
for i in range(8):
    subset=[p for p in parts if p.get('actor',-100) in range(i*4,min((i+1)*4,30))]
    if i==0:subset=[parts[0]]+subset
    if i==7:subset=subset+[parts[-1]]
    text='\n\n'.join(p['text'] for p in subset)
    assert len(text)<=1500,(i,len(text))
    batches.append(dict(index=i,file=f'batch_{i:02d}.wav',parts=[p['id'] for p in subset],text=text))
    print(f'Batch {i}: {len(text)} characters; {len(text.split())} words; '+', '.join(p['id'] for p in subset))
(ROOT/'narrative.json').write_text(json.dumps({'parts':parts,'batches':batches,'chapters':CHAPTERS},indent=2))
(ROOT/'output/Hollywood_Narration.txt').write_text('\n\n'.join(p['caption'] for p in parts))
# Verify named films/characters against the retrieved biographical introductions.
sources=json.loads((ROOT/'research/career_sources.json').read_text())
def norm(t):return re.sub('[^a-z0-9]','',t.lower())
miss=[]
for a,films in zip(actors,FILMS):
    intro=norm(sources[a['name']]['intro'])
    for film in films:
        if norm(film) not in intro:miss.append((a['name'],film))
print('Career references needing additional context:',miss)
(ROOT/'research/career_reference_checks.json').write_text(json.dumps({'not_in_intro':miss},indent=2))
