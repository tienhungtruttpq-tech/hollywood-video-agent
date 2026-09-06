#!/usr/bin/env python3
"""Create the editable manifest for the five Hollywood Then & Now episodes.

The first four episodes reuse only the previously researched Wikimedia Commons
records stored in this repository.  Comedy assets are intentionally represented
by explicit Commons source records rather than uncredited web images.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

NARRATION = {
    "01_leading_men": {
        "a": "Welcome to Hollywood Leading Men, Then and Now. We begin with Tom Cruise. A nineteen eighty nine Oscars portrait catches him just after Top Gun made him a defining movie star. A recent festival image shows the same focused screen presence, now backed by decades of daring action films. Leonardo DiCaprio moved from youthful dramatic roles to an Oscar winning career that includes Titanic, The Departed, and The Revenant. His two portraits trace a performer who keeps choosing ambitious collaborators and very different worlds. Tom Hanks brings another kind of range. From the playful energy of Big to the humanity of Forrest Gump, Apollo 13, and Toy Story, he made warmth feel cinematic. Look closely at these first three pairs, then see which familiar expression has stayed with each actor.",
        "b": "Now for three more leading men. Brad Pitt arrived with a restless edge that carried from Thelma and Louise to Fight Club and Once Upon a Time in Hollywood. The years change the style, but the calm intensity remains easy to recognize. Denzel Washington has brought authority and detail to characters in Glory, Malcolm X, Training Day, and Fences. His portraits frame a career built on listening as carefully as speaking. George Clooney turned television charm into a varied film career, from Ocean's Eleven to Syriana, The Descendants, and directing work behind the camera. Six careers, six different paths through Hollywood. Which early and recent pairing surprised you most?",
    },
    "02_leading_ladies": {
        "a": "Welcome to Hollywood Leading Ladies, Then and Now. Julia Roberts became a global favorite with Pretty Woman, then gave Erin Brockovich a sharp, determined center. Across the years, her famous smile still carries both comedy and conviction. Angelina Jolie has moved between action spectacle, intimate drama, directing, and humanitarian work. Lara Croft, Girl Interrupted, and Maleficent show only a few of the contrasting images in her career. Nicole Kidman has made reinvention part of her screen language. From Moulin Rouge to The Hours, The Others, and Big Little Lies, she can make glamour, suspense, and quiet vulnerability feel equally precise. Compare the early and recent portraits and notice how each actress has reshaped a familiar image.",
        "b": "The next three leading ladies carry that story forward. Kate Winslet made Rose unforgettable in Titanic, then kept seeking complicated characters in films and television dramas. Her work often feels lived in rather than posed. Charlize Theron has crossed from the dramatic transformation of Monster to the physical force of Mad Max Fury Road, proving that range can be both emotional and athletic. Anne Hathaway first introduced many viewers to a shy princess in The Princess Diaries. Later roles in The Devil Wears Prada, Les Miserables, and Interstellar revealed a performer comfortable with wit, music, and depth. Six portraits, six evolving careers. Which role appears in your mind the moment you see each face?",
    },
    "03_action_icons": {
        "a": "Welcome to Action Icons, Then and Now. Arnold Schwarzenegger turned a champion bodybuilder's physical presence into an unmistakable movie persona. The Terminator, Predator, and Total Recall made him a symbol of eighties action, while later work added comedy and public service to the story. Sylvester Stallone created two of cinema's most durable underdogs. Rocky and Rambo began as very different characters, but both carried the determination that made his screen image so lasting. Harrison Ford brought a dry, grounded humor to extraordinary adventures. Han Solo and Indiana Jones remain legendary because he made heroes look brave, skeptical, and human at the same time. These early and later portraits span more than changing hairstyles. They capture how action stardom learned to endure.",
        "b": "The next icons prove that action can take many forms. Samuel L Jackson can turn a few lines into a defining movie moment, from Pulp Fiction to Nick Fury and beyond. His voice, timing, and presence make even an ensemble feel larger. Hugh Jackman brought musical theater energy and fierce physical commitment to Wolverine, then showed another side in The Greatest Showman. Sigourney Weaver changed science fiction with Ripley in Alien, a character defined by intelligence and survival rather than easy stereotypes. Ghostbusters and Avatar later displayed her comedy and imagination. Six action careers, each built on a different kind of strength. Which hero or heroine would you add to the next chapter?",
    },
    "04_nineties_icons": {
        "a": "Welcome to Nineties Hollywood Icons, Then and Now. Winona Ryder made offbeat characters feel instantly memorable in Beetlejuice, Heathers, Edward Scissorhands, and Reality Bites. Stranger Things later introduced her to a new generation without losing that distinctive intensity. Meg Ryan became one of the era's essential romantic comedy stars. When Harry Met Sally and You've Got Mail showed how a pause, a look, or a perfectly timed line can make a love story feel personal. Johnny Depp built an early career around unusual choices, from Edward Scissorhands to Ed Wood and Fear and Loathing in Las Vegas. His portraits reflect an actor drawn to transformation rather than a single predictable type. Take a moment with these images and remember where you first saw them.",
        "b": "The nineties also made room for stars who could move between music, comedy, drama, and action. Will Smith went from The Fresh Prince of Bel Air to Independence Day and Men in Black with an ease that made every new role feel like an event. Halle Berry combined charisma with risk taking performances, from romantic drama to Storm in the X Men films and her Oscar winning work in Monster's Ball. Uma Thurman brought a cool, precise presence to Pulp Fiction, then returned to action in Kill Bill with a completely different kind of force. These six faces helped define a decade, but their later portraits remind us that a cultural moment is only one chapter of a long career.",
    },
    "05_comedy_stars": {
        "a": "Welcome to Comedy Stars, Then and Now. Jim Carrey turned elastic expressions and fearless physical comedy into a signature style in The Mask, Ace Ventura, and Liar Liar. He later surprised audiences with thoughtful dramatic work, showing that a comic persona can hold more than one note. Adam Sandler built a devoted audience with offbeat characters and warm, messy friendships in films such as The Wedding Singer, Happy Gilmore, and Fifty First Dates. His later dramatic roles revealed another layer beneath the familiar humor. Ben Stiller has made awkward confidence a comedy art form, whether leading Zoolander, meeting the in laws, or playing with action movie clichés. Watch the early and later portraits, and think about how much comic timing can live in a single glance.",
        "b": "Comedy has many rhythms. Eddie Murphy became a movie star through bold characters, quick voices, and enormous energy in Trading Places, Beverly Hills Cop, Coming to America, and The Nutty Professor. Steve Carell can make a pause funnier than a punchline, then shift from The Office and Anchorman to deeply human dramatic roles. Melissa McCarthy brings physical precision, improvisational spark, and genuine feeling to Bridesmaids, Spy, Can You Ever Forgive Me, and more. These six careers show that laughter changes with the times, but generosity, timing, and surprise never go out of style. Which comedy performance still makes you laugh before the scene has even started?",
    },
}

# Each visual-card entry is brief enough to remain legible at 1280x720.
CARD_COPY = {
    "Tom Cruise": ("TOP GUN • MISSION: IMPOSSIBLE", "A screen career built around precision, velocity and a very public love of cinema."),
    "Leonardo DiCaprio": ("TITANIC • THE REVENANT", "From a young dramatic lead to an Oscar-winning collaborator with major filmmakers."),
    "Tom Hanks": ("BIG • FORREST GUMP • TOY STORY", "Warmth, humor and emotional clarity made ordinary people feel unforgettable."),
    "Brad Pitt": ("FIGHT CLUB • ONCE UPON A TIME IN HOLLYWOOD", "A restless screen presence that keeps moving between movie-star scale and character detail."),
    "Denzel Washington": ("GLORY • MALCOLM X • FENCES", "Commanding performances built from restraint, rhythm and close attention to character."),
    "George Clooney": ("OCEAN'S ELEVEN • THE DESCENDANTS", "Charm became a bridge to drama, producing and directing."),
    "Julia Roberts": ("PRETTY WOMAN • ERIN BROCKOVICH", "A familiar smile that can land a joke or sharpen a moment of conviction."),
    "Angelina Jolie": ("GIRL, INTERRUPTED • MALEFICENT", "A career that crosses intimate drama, mythic spectacle and work behind the camera."),
    "Nicole Kidman": ("MOULIN ROUGE • THE HOURS", "Glamour, suspense and vulnerability become different tools in each new role."),
    "Kate Winslet": ("TITANIC • MARE OF EASTTOWN", "A performer drawn to characters that feel lived in rather than merely polished."),
    "Charlize Theron": ("MONSTER • MAD MAX: FURY ROAD", "Range that is both emotionally exacting and physically fearless."),
    "Anne Hathaway": ("THE PRINCESS DIARIES • INTERSTELLAR", "From quick wit and musical drama to high-stakes science fiction."),
    "Arnold Schwarzenegger": ("THE TERMINATOR • PREDATOR", "A physical icon whose later chapters include comedy and public service."),
    "Sylvester Stallone": ("ROCKY • RAMBO", "Two different underdogs, both carried by unwavering determination."),
    "Harrison Ford": ("STAR WARS • INDIANA JONES", "Adventure heroes made memorable by dry humor, skepticism and nerve."),
    "Samuel L. Jackson": ("PULP FICTION • NICK FURY", "Voice, timing and presence that can make an ensemble feel larger."),
    "Hugh Jackman": ("WOLVERINE • THE GREATEST SHOWMAN", "Musical-theater energy meets fierce physical commitment."),
    "Sigourney Weaver": ("ALIEN • GHOSTBUSTERS • AVATAR", "Science fiction, comedy and imagination in one singular screen career."),
    "Winona Ryder": ("BEETLEJUICE • STRANGER THINGS", "A defining face of offbeat cinema, rediscovered by a new generation."),
    "Meg Ryan": ("WHEN HARRY MET SALLY • YOU'VE GOT MAIL", "Romantic comedy powered by timing, warmth and the perfect pause."),
    "Johnny Depp": ("EDWARD SCISSORHANDS • ED WOOD", "An early career defined by transformations rather than predictability."),
    "Will Smith": ("THE FRESH PRINCE • MEN IN BLACK", "Music, television, action and comedy met in a star with event-movie energy."),
    "Halle Berry": ("MONSTER'S BALL • X-MEN", "Charisma, risk-taking and a willingness to change genres."),
    "Uma Thurman": ("PULP FICTION • KILL BILL", "Cool precision and physical force, used in entirely different ways."),
    "Jim Carrey": ("THE MASK • LIAR LIAR", "Fearless physical comedy, then unexpected turns toward quieter drama."),
    "Adam Sandler": ("HAPPY GILMORE • THE WEDDING SINGER", "Offbeat characters, warm friendships and a dramatic side beneath the laughs."),
    "Ben Stiller": ("ZOOLANDER • MEET THE PARENTS", "Awkward confidence turned into a precise and enduring comic language."),
    "Eddie Murphy": ("TRADING PLACES • COMING TO AMERICA", "Big characters, quick voices and enough energy to fill a frame."),
    "Steve Carell": ("THE OFFICE • ANCHORMAN", "A pause can be funnier than a punchline, and just as moving."),
    "Melissa McCarthy": ("BRIDESMAIDS • SPY", "Physical precision, improvisational spark and genuine feeling."),
}

# Origin values load the verified source record from the existing repository.
EPISODE_SELECTIONS = [
    {
        "id": "01_leading_men", "number": 1,
        "title": "HOLLYWOOD LEADING MEN", "strapline": "THEN & NOW",
        "accent": [69, 202, 238], "accent2": [113, 90, 238],
        "filename": "01_Hollywood_Leading_Men_Then_Now.mp4",
        "origin": "full",
        "people": [0, 1, 2, 3, 6, 7],
    },
    {
        "id": "02_leading_ladies", "number": 2,
        "title": "HOLLYWOOD LEADING LADIES", "strapline": "THEN & NOW",
        "accent": [248, 115, 188], "accent2": [132, 94, 194],
        "filename": "02_Hollywood_Leading_Ladies_Then_Now.mp4",
        "origin": "actresses",
        "people": [0, 1, 2, 3, 10, 14],
    },
    {
        "id": "03_action_icons", "number": 3,
        "title": "ACTION MOVIE ICONS", "strapline": "THEN & NOW",
        "accent": [250, 153, 55], "accent2": [239, 68, 68],
        "filename": "03_Action_Movie_Icons_Then_Now.mp4",
        "people": [("full", 20), ("full", 21), ("full", 12), ("full", 19), ("full", 23), ("actresses", 21)],
    },
    {
        "id": "04_nineties_icons", "number": 4,
        "title": "NINETIES HOLLYWOOD ICONS", "strapline": "THEN & NOW",
        "accent": [34, 211, 238], "accent2": [236, 72, 153],
        "filename": "04_Nineties_Hollywood_Icons_Then_Now.mp4",
        "people": [("actresses", 6), ("actresses", 8), ("full", 5), ("full", 10), ("actresses", 9), ("actresses", 19)],
    },
]

# Source fields for this episode are filled with Commons metadata after assets are
# acquired. The immutable file paths below are the contract used by the renderer.
COMEDY_PEOPLE = [
    ("Jim Carrey", "comedy_jim_carrey", [1994, 2025]),
    ("Adam Sandler", "comedy_adam_sandler", [1995, 2025]),
    ("Ben Stiller", "comedy_ben_stiller", [1996, 2025]),
    ("Eddie Murphy", "comedy_eddie_murphy", [1983, 2025]),
    ("Steve Carell", "comedy_steve_carell", [2005, 2025]),
    ("Melissa McCarthy", "comedy_melissa_mccarthy", [2011, 2025]),
]


def asset_path(episode_id: str, person_index: int, era: str) -> str:
    return f"assets/photos/{episode_id}/{person_index:02d}_{era}.jpg"


def source_record(actor: dict, episode_id: str, person_index: int) -> dict:
    rec = copy.deepcopy(actor)
    rec["assets"] = {
        "then": asset_path(episode_id, person_index, "then"),
        "now": asset_path(episode_id, person_index, "now"),
    }
    rec["card_copy"] = list(CARD_COPY[rec["name"]])
    return rec


def placeholder_record(name: str, key: str, years: list[int], episode_id: str, person_index: int) -> dict:
    # All Commons facts are filled by source_comedy_assets.py before rendering.
    return {
        "name": name,
        "key": key,
        "years": years,
        "then": {"year": years[0], "source": "", "title": "", "artist": "", "license": "", "license_url": ""},
        "now": {"year": years[1], "source": "", "title": "", "artist": "", "license": "", "license_url": ""},
        "assets": {
            "then": asset_path(episode_id, person_index, "then"),
            "now": asset_path(episode_id, person_index, "now"),
        },
        "card_copy": list(CARD_COPY[name]),
    }


def main() -> None:
    full = json.loads((REPO / "hollywood_full" / "actors.json").read_text(encoding="utf-8"))
    actresses = json.loads((REPO / "hollywood_actresses" / "actors.json").read_text(encoding="utf-8"))
    origins = {"full": full, "actresses": actresses}

    episodes = []
    for selection in EPISODE_SELECTIONS:
        ep = {k: copy.deepcopy(v) for k, v in selection.items() if k not in {"origin", "people"}}
        people = []
        default_origin = selection.get("origin")
        for person_index, value in enumerate(selection["people"]):
            origin, source_index = (default_origin, value) if isinstance(value, int) else value
            people.append(source_record(origins[origin][source_index], ep["id"], person_index))
        ep["people"] = people
        ep["narration"] = NARRATION[ep["id"]]
        ep["audio"] = {
            "a": f"assets/audio/{ep['id']}_a.mp3",
            "b": f"assets/audio/{ep['id']}_b.mp3",
        }
        episodes.append(ep)

    comedy = {
        "id": "05_comedy_stars", "number": 5,
        "title": "HOLLYWOOD COMEDY STARS", "strapline": "THEN & NOW",
        "accent": [250, 204, 21], "accent2": [249, 115, 22],
        "filename": "05_Hollywood_Comedy_Stars_Then_Now.mp4",
        "people": [placeholder_record(name, key, years, "05_comedy_stars", i) for i, (name, key, years) in enumerate(COMEDY_PEOPLE)],
        "narration": NARRATION["05_comedy_stars"],
        "audio": {"a": "assets/audio/05_comedy_stars_a.mp3", "b": "assets/audio/05_comedy_stars_b.mp3"},
    }
    episodes.append(comedy)

    manifest = {
        "format": {"width": 1280, "height": 720, "fps": 24, "duration_seconds": 480, "language": "en"},
        "series": "Hollywood Then & Now — Five-Episode Collection",
        "voice": "voice-00 selected by the user via Arena speech synthesis",
        "music": "Original procedural ambient score generated in batch5/render_batch.py",
        "episodes": episodes,
    }
    out = ROOT / "episodes.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    narration_dir = ROOT / "manifests" / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    for ep in episodes:
        for part in ("a", "b"):
            (narration_dir / f"{ep['id']}_{part}.txt").write_text(ep["narration"][part] + "\n", encoding="utf-8")
    print(f"Wrote {out} with {len(episodes)} episodes.")


if __name__ == "__main__":
    main()
