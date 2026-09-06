from pathlib import Path
import json,re,unicodedata
ROOT=Path(__file__).resolve().parent
TEXTS=[
"Julia Roberts. Pretty Woman made her a global star; Erin Brockovich brought an Oscar. Two different kinds of strength, one familiar smile. One point if you guessed correctly.",
"Angelina Jolie. Lara Croft and Maleficent are easy to remember. But her Oscar-winning performance in Girl, Interrupted is a reminder that the action-star image is only part of the story.",
"Nicole Kidman. Moulin Rouge and The Hours could hardly feel more different. From musical spectacle to intimate character drama, changing direction has become part of her appeal.",
"Kate Winslet. Titanic made Rose part of movie history. Mare of Easttown later traded sweeping romance for a small-town mystery. She can make both worlds feel lived in.",
"Sandra Bullock. Speed needed an action lead; Miss Congeniality needed comic timing. Her appeal connects the two: even in unlikely situations, her characters can feel like someone you know.",
"Cameron Diaz. The Mask and There's Something About Mary are familiar starting points. But many viewers also grew up with her voice as Princess Fiona in Shrek. Did that clue help?",
"Winona Ryder. Beetlejuice and Edward Scissorhands made her a defining face of offbeat cinema. Stranger Things later introduced her to another generation. A career can find a whole new audience.",
"Demi Moore. Ghost became a pop-culture landmark. Decades later, The Substance put fame and appearances at the centre of her work again. A career doesn't have to end with its first peak.",
"Meg Ryan. When Harry Met Sally and You've Got Mail made conversation feel cinematic. Her comedy often lives in the timing: a pause, a glance, a slightly awkward moment.",
"Halle Berry. Storm made her a superhero; Monster's Ball brought an Oscar. Those roles ask for very different kinds of presence. Her filmography is more varied than any single label.",
"Charlize Theron. Monster and Mad Max, Fury Road make an unusual double bill. One leans on intimate character work, the other on physical intensity. She makes space for both.",
"Sharon Stone. Casino earned her an Oscar nomination. It also shows why an actress associated with glamour can be so compelling when a character's carefully built world starts falling apart.",
"Salma Hayek. Desperado showed her charisma; Frida put her inside a painter's story. She also helped bring Frida to the screen as a producer, not just as its leading actress.",
"Cate Blanchett. Elizabeth, The Lord of the Rings and Tar all give her characters authority. But the queen, the elf and the conductor use their power in very different ways.",
"Anne Hathaway. Genovia's princess later became Catwoman, then Fantine in Les Miserables. Those changes show how far a familiar face can travel without staying inside one comfortable genre.",
"Natalie Portman. A queen in Star Wars, a dancer in Black Swan, and a scientist in Thor. Three very different characters, connected by a performer who keeps changing direction.",
"Scarlett Johansson. In Her, she built a character using only her voice. Black Widow needed a different kind of presence. Same performer, completely different tools. Which role came to mind first?",
"Penelope Cruz. Volver and Vicky Cristina Barcelona show different sides of her screen presence. Moving between Spanish-language cinema and Hollywood has made that range an important part of her career.",
"Lucy Liu. Charlie's Angels made her an action favorite. Elementary then gave her a long-running role as Joan Watson. Two different formats, with the same sharp sense of character.",
"Uma Thurman. The dance floor in Pulp Fiction and the action of Kill Bill are hard to confuse. Yet both turn timing and physical presence into something instantly memorable.",
"Jodie Foster. The Silence of the Lambs made Clarice Starling iconic. She's also directed films, adding another viewpoint to a career that began in childhood. The story extends beyond acting.",
"Sigourney Weaver. Ripley in Alien became a science-fiction landmark. Ghostbusters revealed her comic side, and Avatar opened another world. That's a lot of movie history in one familiar face.",
"Jamie Lee Curtis. Halloween made her a horror icon. Everything Everywhere All at Once brought an Oscar decades later. The contrast is a good reminder: an actor can keep surprising us.",
"Meryl Streep. Sophie's Choice and The Devil Wears Prada give us very different versions of her talent. Part of the pleasure is never knowing exactly who she'll become in the next role."
]
HINTS=['Rom-com royalty','An adventurer. A fairy-tale villain.','A musical. A literary drama.','A ship. A small-town detective.','A speeding bus. An undercover pageant.','Comedy... and a fairy-tale princess.','Offbeat cinema. A supernatural TV hit.','A ghost story. A bold new chapter.','Love, laughter... and email.','A superhero. An Oscar-winning drama.','A desert warrior. A dramatic transformation.','Thrillers. Glamour. A casino.','An action star... and a painter.','A queen. An elf. A conductor.','Genovia... then Gotham.','A queen. A dancer. A scientist.','A superhero... and a voice-only role.','Spanish drama. Hollywood comedy.','An angel. A detective.','A dance floor. A yellow jumpsuit.','An FBI trainee... and a director.','A space survivor. A comedy legend.','A scream queen. An Oscar winner.','Fashion. Music. Fearless drama.']
FILMS=[['Pretty Woman','Erin Brockovich'],['Lara Croft','Maleficent','Girl, Interrupted'],['Moulin Rouge','The Hours'],['Titanic','Mare of Easttown'],['Speed','Miss Congeniality'],['The Mask',"There's Something About Mary",'Shrek'],['Beetlejuice','Edward Scissorhands','Stranger Things'],['Ghost','The Substance'],['When Harry Met Sally',"You've Got Mail"],['Storm',"Monster's Ball"],['Monster','Mad Max: Fury Road'],['Casino'],['Desperado','Frida'],['Elizabeth','The Lord of the Rings','Tár'],['The Princess Diaries','Catwoman','Les Misérables'],['Star Wars','Black Swan','Thor'],['Her','Black Widow'],['Volver','Vicky Cristina Barcelona'],["Charlie's Angels",'Elementary'],['Pulp Fiction','Kill Bill'],['The Silence of the Lambs'],['Alien','Ghostbusters','Avatar'],['Halloween','Everything Everywhere All at Once'],["Sophie's Choice",'The Devil Wears Prada']]
ROUNDS=['THE OPENING SIX','MOVIE MEMORIES','CHANGING ROLES','THE FINAL SIX']
INTRO='Name the actress. Three seconds. Go.'
OUTRO='Your score out of twenty-four? Which face surprised you most?'
actors=json.loads((ROOT/'actors.json').read_text())
parts=[dict(id='intro',kind='intro',text=INTRO,caption=INTRO,start=0.,duration=3.,lead=.12,guess=0)]
t=3.
for i,(a,text,hint,films) in enumerate(zip(actors,TEXTS,HINTS,FILMS)):
 if i in [6,12,18]:
  n=i//6;line=['','Round two.','Halfway. Round three.','The final round.'][n]
  parts.append(dict(id=f'round_{n+1}',kind='interlude',text=line,caption=line,start=t,duration=2.,lead=.1,guess=0,round=n));t+=2.
 cap=text.replace('Penelope Cruz','Penélope Cruz').replace('and Tar all','and Tár all').replace('Les Miserables','Les Misérables').replace('Mad Max, Fury Road','Mad Max: Fury Road')
 parts.append(dict(id=f'actress_{i:02d}',kind='actress',actor=i,name=a['name'],text=text,caption=cap,start=t,duration=19.,lead=.34,guess=0. if i==0 else 3.,hint=hint,films=films,round=i//6));t+=19.
parts.append(dict(id='outro',kind='outro',text=OUTRO,caption=OUTRO,start=t,duration=5.,lead=.15,guess=0));t+=5
assert t==470,t
# Six independent narration calls. No new voice audition is needed.
batches=[];current=[];actor_count=0
for part in parts:
 current.append(part)
 if part['kind']=='actress':actor_count+=1
 if actor_count==4 and part['id']!='actress_23':
  text='\n\n'.join(p['text'] for p in current);batches.append(dict(index=len(batches),file=f'batch_{len(batches):02d}.wav',parts=[p['id'] for p in current],text=text));current=[];actor_count=0
if current:
 text='\n\n'.join(p['text'] for p in current);batches.append(dict(index=len(batches),file=f'batch_{len(batches):02d}.wav',parts=[p['id'] for p in current],text=text))
assert len(batches)==6
for b in batches:assert len(b['text'])<=1500,(b['index'],len(b['text']))
(ROOT/'narrative.json').write_text(json.dumps(dict(parts=parts,batches=batches,rounds=ROUNDS,duration=480),ensure_ascii=False,indent=2))
(ROOT/'output/Actresses_English_Script.txt').write_text('\n\n'.join(p['caption'] for p in parts))
# Film/character facts are grounded in retrieved biographies; interpretive
# observations about performances are original commentary, not measured claims.
sources=json.loads((ROOT/'research/career_sources.json').read_text())
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
miss=[]
for a,films in zip(actors,FILMS):
 for f in films:
  if norm(f) not in norm(sources[a['name']]['intro']):miss.append([a['name'],f])
(ROOT/'research/fact_check_queue.json').write_text(json.dumps(miss,indent=2))
print('Named roles/films needing full-filmography context:',miss)
for b in batches:print('\nBATCH',b['index'],len(b['text']),'characters\n'+b['text'])
