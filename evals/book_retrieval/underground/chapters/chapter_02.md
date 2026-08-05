# Chapter 2: The Corner Pub.

CHAPTER 2 — The Corner Pub.
You talk of times of peace for all; and then prepare for war.
— from `Blossom of Blood', Species Deceases.
It is not surprising the SPAN security team would miss the mark. It is
not surprising, for example, that these officials should to this day
be pronouncing the `Oilz' version of the WANK worm as `oil zee'. It is
also not surprising that they hypothesised the worm's creator chose
the word `Oilz' because the modifications made to the last version
made it slippery, perhaps even oily.
Likely as not, only an Australian would see the worm's link to the
lyrics of Midnight Oil.
This was the world's first worm with a political message, and the
second major worm in the history of the worldwide computer networks.
It was also the trigger for the creation of FIRST, the Forum of
Incident Response and Security Teams.2 FIRST was an international
security alliance allowing governments, universities and commercial
organisations to share information about computer network security
incidents. Yet, NASA and the US Department of Energy were half a world
away from finding the creator of the WANK worm. Even as investigators
sniffed around electronic trails leading to France, it appears the
perpetrator was hiding behind his computer and modem in Australia.
Geographically, Australia is a long way from anywhere. To Americans,
it conjures up images of fuzzy marsupials, not computer hackers.
American computer security officials, like those at NASA and the US
Department of Energy, had other barriers as well. They function in a
world of concretes, of appointments made and kept, of real names,
business cards and official titles. The computer underground, by
contrast, is a veiled world populated by characters slipping in and
out of the half-darkness. It is not a place where people use their
real names. It is not a place where people give out real personal
details.
It is, in fact, not so much a place as a space. It is ephemeral,
intangible—a foggy labyrinth of unmapped, winding streets through
which one occasionally ascertains the contours of a fellow traveller.
When Ron Tencati, the manager in charge of NASA SPAN security, realised
that NASA's computers were being attacked by an intruder, he rang the
FBI. The US Federal Bureau of Investigation's Computer Crime Unit fired
off a stream of questions. How many computers had been attacked? Where
were they? Who was behind the attack? The FBI told Tencati, `keep us
informed of the situation'. Like the CIAC team in the Department of
Energy, it appears the FBI didn't have much knowledge of VMS, the
primary computer operating system used in SPAN.
But the FBI knew enough to realise the worm attack was potentially
very serious. The winding electronic trail pointed vaguely to a
foreign computer system and, before long, the US Secret Service was
involved. Then the French secret service, the Direction de la
Surveillance du Territoire, or DST, jumped into the fray.
DST and the FBI began working together on the case. A casual observer
with the benefit of hindsight might see different motivations driving
the two government agencies. The FBI wanted to catch the perpetrator.
The DST wanted to make it clear that the infamous WANK worm attack on
the world's most prestigious space agency did not originate in France.
In the best tradition of cloak-and-dagger government agencies, the FBI
and DST people established two communication channels—an official
channel and an unofficial one. The official channel involved
embassies, attachés, formal communiques and interminable delays in
getting answers to the simplest questions. The unofficial channel
involved a few phone calls and some fast answers.
Ron Tencati had a colleague named Chris on the SPAN network in France,
which was the largest user of SPAN in Europe. Chris was involved in
more than just science computer networks. He had certain contacts in
the French government and seemed to be involved in their computer
networks. So, when the FBI needed technical information for its
investigation—the kind of information likely to be sanitised by some
embassy bureaucrat—one of its agents rang up Ron Tencati. `Ron, ask
your friend this,' the FBI would say. And Ron would.
`Chris, the FBI wants to know this,' Tencati would tell his colleague
on SPAN France. Then Chris would get the necessary information. He
would call Tencati back, saying, `Ron, here is the answer. Now, the
DST wants to know that'. And off Ron would go in search of information
requested by the DST.
The investigation proceeded in this way, with each helping the other
through backdoor channels. But the Americans' investigation was headed
toward the inescapable conclusion that the attack on NASA had
originated from a French computer. The worm may have simply travelled
through the French computer from yet another system, but the French
machine appeared to be the sole point of infection for NASA.
The French did not like this outcome. Not one bit. There was no way
that the worm had come from France. Ce n'est pas vrai.
Word came back from the French that they were sure the worm had come
from the US. Why else would it have been programmed to mail details of
all computer accounts it penetrated around the world back to a US
machine, the computer known as GEMPAK? Because the author of the worm
was an American, of course! Therefore it is not our problem, the
French told the Americans. It is your problem.
Most computer security experts know it is standard practice among
hackers to create the most tangled trail possible between the hacker
and the hacked. It makes it very difficult for people like the FBI to
trace who did it. So it would be difficult to draw definite
conclusions about the nationality of the hacker from the location of a
hacker's information drop-off point—a location the hacker no doubt
figured would be investigated by the authorities almost immediately
after the worm's release.
Tencati had established the French connection from some computer logs
showing NASA under attack very early on Monday, 16 October. The logs
were important because they were relatively clear. As the worm had
procreated during that day, it had forced computers all over the
network to attack each other in ever greater numbers. By 11 a.m. it
was almost impossible to tell where any one attack began and the other
ended.
Some time after the first attack, DST sent word that certain agents
were going to be in Washington DC regarding other matters. They wanted
a meeting with the FBI. A representative from the NASA Inspector
General's Office would attend the meeting, as would someone from NASA
SPAN security.
Tencati was sure he could show the WANK worm attack on NASA originated
in France. But he also knew he had to document everything, to have
exact answers to every question and counter-argument put forward by
the French secret service agents at the FBI meeting. When he developed
a timeline of attacks, he found that the GEMPAK machine showed X.25
network connection, via another system, from a French computer around
the same time as the WANK worm attack. He followed the scent and
contacted the manager of that system. Would he help Tencati? Mais oui.
The machine is at your disposal, Monsieur Tencati.
Tencati had never used an X.25 network before; it had a unique set of
commands unlike any other type of computer communications network. He
wanted to retrace the steps of the worm, but he needed help. So he
called his friend Bob Lyons at DEC to walk him through the process.
What Tencati found startled him. There were traces of the worm on the
machine all right, the familiar pattern of login failures as the worm
attempted to break into different accounts. But these remnants of the
WANK worm were not dated 16 October or any time immediately around
then. The logs showed worm-related activity up to two weeks before the
attack on NASA. This computer was not just a pass-through machine the
worm had used to launch its first attack on NASA. This was the
development machine.
Ground zero.
Tencati went into the meeting with DST at the FBI offices prepared. He
knew the accusations the French were going to put forward. When he
presented the results of his sleuthwork, the French secret service
couldn't refute it, but they dropped their own bombshell. Yes they
told him, you might be able to point to a French system as ground zero
for the attack, but our investigations reveal incoming X.25
connections from elsewhere which coincided with the timing of the
development of the WANK worm.
The connections came from Australia.
The French had satisfied themselves that it wasn't a French hacker who
had created the WANK worm. Ce n'est pas notre problem. At least, it's
not our problem any more.
It is here that the trail begins to go cold. Law enforcement and
computer security people in the US and Australia had ideas about just
who had created the WANK worm. Fingers were pointed, accusations were
made, but none stuck. At the end of the day, there was coincidence and
innuendo, but not enough evidence to launch a case. Like many
Australian hackers, the creator of the WANK worm had emerged from the
shadows of the computer underground, stood momentarily in hazy
silhouette, and then disappeared again.
The Australian computer underground in the late 1980s was an
environment which spawned and shaped the author of the WANK worm.
Affordable home computers, such as the Apple IIe and the Commodore 64,
made their way into ordinary suburban families. While these computers
were not widespread, they were at least in a price range which made
them attainable by dedicated computer enthusiasts.
In 1988, the year before the WANK worm attack on NASA, Australia was
on an upswing. The country was celebrating its bicentennial. The
economy was booming. Trade barriers and old regulatory structures were
coming down. Crocodile Dundee had already burst on the world movie
scene and was making Australians the flavour of the month in cities
like LA and New York. The mood was optimistic. People had a sense they
were going places. Australia, a peaceful country of seventeen or so
million people, poised on the edge of Asia but with the order of a
Western European democracy, was on its way up. Perhaps for the first
time, Australians had lost their cultural cringe, a unique type of
insecurity alien to can-do cultures such as that found in the US.
Exploration and experimentation require confidence and, in 1988,
confidence was something Australia had finally attained.
Yet this new-found confidence and optimism did not subdue Australia's
tradition of cynicism toward large institutions. The two coexisted,
suspended in a strange paradox. Australian humour, deeply rooted in a
scepticism of all things serious and sacred, continued to poke fun at
upright institutions with a depth of irreverence surprising to many
foreigners. This cynicism of large, respected institutions coursed
through the newly formed Australian computer underground without
dampening its excitement or optimism for the brave new world of
computers in the least.
In 1988, the Australian computer underground thrived like a vibrant
Asian street bazaar. In that year it was still a realm of place not
space. Customers visited their regular stalls, haggled over goods with
vendors, bumped into friends and waved across crowded paths to
acquaintances. The market was as much a place to socialise as it was
to shop. People ducked into tiny coffee houses or corner bars for
intimate chats. The latest imported goods, laid out on tables like
reams of bright Chinese silks, served as conversation starters. And,
like every street market, many of the best items were tucked away,
hidden in anticipation of the appearance of that one customer or
friend most favoured by the trader. The currency of the underground
was not money; it was information. People didn't share and exchange
information to accumulate monetary wealth; they did it to win
respect—and to buy a thrill.
The members of the Australian computer underground met on bulletin
board systems, known as BBSes. Simple things by today's standards,
BBSes were often composed of a souped-up Apple II computer, a single
modem and a lone telephone line. But they drew people from all walks
of life. Teenagers from working-class neighbourhoods and those from
the exclusive private schools. University students. People in their
twenties groping their way through first jobs. Even some professional
people in their thirties and forties who spent weekends poring over
computer manuals and building primitive computers in spare rooms. Most
regular BBS users were male. Sometimes a user's sister would find her
way into the BBS world, often in search of a boyfriend. Mission
accomplished, she might disappear from the scene for weeks, perhaps
months, presumably until she required another visit.
The BBS users had a few things in common. They were generally of above
average intelligence—usually with a strong technical slant—and they
were obsessed with their chosen hobby. They had to be. It often took
45 minutes of attack dialling a busy BBS's lone phone line just to
visit the computer system for perhaps half an hour. Most serious BBS
hobbyists went through this routine several times each day.
As the name suggests, a BBS had what amounted to an electronic version
of a normal bulletin board. The owner of the BBS would have divided
the board into different areas, as a school teacher crisscrosses
coloured ribbon across the surface of a corkboard to divide it into
sections. A single BBS might have 30 or more electronic discussion
groups.
As a user to the board, you might visit the politics section, tacking
up a `note' on your views of ALP or Liberal policies for anyone
passing by to read. Alternatively, you might fancy yourself a bit of a
poet and work up the courage to post an original piece of work in the
Poet's Corner. The corner was often filled with dark, misanthropic
works inspired by the miseries of adolescence. Perhaps you preferred
to discuss music. On many BBSes you could find postings on virtually
any type of music. The most popular groups included bands like Pink
Floyd, Tangerine Dream and Midnight Oil. Midnight Oil's
anti-establishment message struck a particular chord within the new
BBS community.
Nineteen eighty-eight was the golden age of the BBS culture across
Australia. It was an age of innocence and community, an open-air
bazaar full of vitality and the sharing of ideas. For the most part,
people trusted their peers within the community and the BBS operators,
who were often revered as demigods. It was a happy place. And, in
general, it was a safe place, which is perhaps one reason why its
visitors felt secure in their explorations of new ideas. It was a
place in which the creator of the WANK worm could sculpt and hone his
creative computer skills.
The capital of this spirited new Australian electronic civilisation
was Melbourne. It is difficult to say why this southern city became
the cultural centre of the BBS world, and its darker side, the
Australian computer underground. Maybe the city's history as
Australia's intellectual centre created a breeding ground for the many
young people who built their systems with little more than curiosity
and salvaged computer bits discarded by others. Maybe Melbourne's
personality as a city of suburban homebodies and backyard tinkerers
produced a culture conducive to BBSes. Or maybe it was just
Melbourne's dreary beaches and often miserable weather. As one
Melbourne hacker explained it, `What else is there to do here all
winter but hibernate inside with your computer and modem?'
In 1988, Melbourne had some 60 to 100 operating BBSes. The numbers are
vague because it is difficult to count a collection of moving objects.
The amateur nature of the systems, often a jumbled tangle of wires and
second-hand electronics parts soldered together in someone's garage,
meant that the life of any one system was frequently as short as a
teenager's attention span. BBSes popped up, ran for two weeks, and
then vanished again.
Some of them operated only during certain hours, say between 10 p.m.
and 8 a.m. When the owner went to bed, he or she would plug the home
phone line into the BBS and leave it there until morning. Others ran
24 hours a day, but the busiest times were always at night.
Of course it wasn't just intellectual stimulation some users were
after. Visitors often sought identity as much as ideas. On an
electronic bulletin board, you could create a personality, mould it
into shape and make it your own. Age and appearance did not matter.
Technical aptitude did. Any spotty, gawky teenage boy could instantly
transform himself into a suave, graceful BBS character. The
transformation began with the choice of name. In real life, you might
be stuck with the name Elliot Dingle—an appellation chosen by your
mother to honour a long-dead great uncle. But on a BBS, well, you
could be Blade Runner, Ned Kelly or Mad Max. Small wonder that, given
the choice, many teenage boys chose to spend their time in the world
of the BBS.
Generally, once a user chose a handle, as the on-line names are known,
he stuck with it. All his electronic mail came to an account with that
name on it. Postings to bulletin boards were signed with it. Others
dwelling in the system world knew him by that name and no other. A
handle evolved into a name laden with innate meaning, though the
personality reflected in it might well have been an alter ego. And so
it was that characters like The Wizard, Conan and Iceman came to pass
their time on BBSes like the Crystal Palace, Megaworks, The Real
Connection and Electric Dreams.
What such visitors valued about the BBS varied greatly. Some wanted to
participate in its social life. They wanted to meet people like
themselves—bright but geeky or misanthropic people who shared an
interest in the finer technical points of computers. Many lived as
outcasts in real life, never quite making it into the `normal' groups
of friends at school or uni. Though some had started their first jobs,
they hadn't managed to shake the daggy awkwardness which pursued them
throughout their teen years. On the surface, they were just not the
sort of people one asked out to the pub for a cold one after the
footy.
But that was all right. In general, they weren't much interested in
footy anyway.
Each BBS had its own style. Some were completely legitimate, with
their wares—all legal goods—laid out in the open. Others, like The
Real Connection, had once housed Australia's earliest hackers but had
gone straight. They closed up the hacking parts of the board before
the first Commonwealth government hacking laws were enacted in June
1989. Perhaps ten or twelve of Melbourne's BBSes at the time had the
secret, smoky flavour of the computer underground. A handful of these
were invitation-only boards, places like Greyhawk and The Realm. You
couldn't simply ring up the board, create a new account and login. You
had to be invited by the board's owner. Members of the general
modeming public need not apply.
The two most important hubs in the Australian underground between 1987
and 1989 were named Pacific Island and Zen. A 23-year-old who called
himself Craig Bowen ran both systems from his bedroom.
Also known as Thunderbird1, Bowen started up Pacific Island in 1987
because he wanted a hub for hackers. The fledgling hacking community
was dispersed after AHUBBS, possibly Melbourne's earliest hacking
board, faded away. Bowen decided to create a home for it, a sort of
dark, womb-like cafe bar amid the bustle of the BBS bazaar where
Melbourne's hackers could gather and share information.
His bedroom was a simple, boyish place. Built-in cupboards, a bed, a
wallpaper design of vintage cars running across one side of the room.
A window overlooking the neighbours' leafy suburban yard. A collection
of PC magazines with titles like Nibble and Byte. A few volumes on
computer programming. VAX/VMS manuals. Not many books, but a handful
of science fiction works by Arthur C. Clarke. The Hitchhiker's Guide
to the Galaxy. A Chinese-language dictionary used during his high
school Mandarin classes, and after, as he continued to study the
language on his own while he held down his first job.
The Apple IIe, modem and telephone line rested on the drop-down
drawing table and fold-up card table at the foot of his bed. Bowen put
his TV next to the computer so he could sit in bed, watch TV and use
Pacific Island all at the same time. Later, when he started Zen, it
sat next to Pacific Island. It was the perfect set-up.
Pacific Island was hardly fancy by today's standards of Unix Internet
machines, but in 1987 it was an impressive computer. PI, pronounced
`pie' by the local users, had a 20 megabyte hard drive—gargantuan for
a personal computer at the time. Bowen spent about $5000 setting up PI
alone. He loved both systems and spent many hours each week nurturing
them.
There was no charge for computer accounts on PI or ZEN, like most
BBSes. This gentle-faced youth, a half-boy, half-man who would
eventually play host on his humble BBS to many of Australia's
cleverest computer and telephone hackers, could afford to pay for his
computers for two reasons: he lived at home with his mum and dad, and
he had a full-time job at Telecom—then the only domestic telephone
carrier in Australia.
PI had about 800 computer users, up to 200 of whom were `core' users
accessing the system regularly. PI had its own dedicated phone line,
separate from the house phone so Bowen's parents wouldn't get upset the
line was always tied up. Later, he put in four additional phone lines
for Zen, which had about 2000 users. Using his Telecom training, he
installed a number of non-standard, but legal, features to his
house. Junction boxes, master switches. Bowen's house was a
telecommunications hot-rod.
Bowen had decided early on that if he wanted to keep his job, he had
better not do anything illegal when it came to Telecom. However, the
Australian national telecommunications carrier was a handy source of
technical information. For example, he had an account on a Telecom
computer system—for work—from which he could learn about Telecom's
exchanges. But he never used that account for hacking. Most
respectable hackers followed a similar philosophy. Some had legitimate
university computer accounts for their courses, but they kept those
accounts clean. A basic rule of the underground, in the words of one
hacker, was `Don't foul your own nest'.
PI contained a public section and a private one. The public area was
like an old-time pub. Anyone could wander in, plop down at the bar and
start up a conversation with a group of locals. Just ring up the
system with your modem and type in your details—real name, your
chosen handle, phone number and other basic information.
Many BBS users gave false information in order to hide their true
identities, and many operators didn't really care. Bowen, however,
did. Running a hacker's board carried some risk, even before the
federal computer crime laws came into force. Pirated software was
illegal. Storing data copied from hacking adventures in foreign
computers might also be considered illegal. In an effort to exclude
police and media spies, Bowen tried to verify the personal details of
every user on PI by ringing them at home or work. Often he was
successful. Sometimes he wasn't.
The public section of PI housed discussion groups on the major PC
brands—IBM, Commodore, Amiga, Apple and Atari—next to the popular
Lonely Hearts group. Lonely Hearts had about twenty regulars, most of
whom agonised under the weight of pubescent hormonal changes. A boy
pining for the affections of the girl who dumped him or, worse, didn't
even know he existed. Teenagers who contemplated suicide. The messages
were completely anonymous, readers didn't even know the authors'
handles, and that anonymous setting allowed heart-felt messages and
genuine responses.
Zen was PI's sophisticated younger sister. Within two years of PI
making its debut, Bowen opened up Zen, one of the first Australian
BBSes with more than one telephone line. The main reason he set up Zen
was to stop his computer users from bothering him all the time. When
someone logged into PI, one of the first things he or she did was
request an on-line chat with the system operator. PI's Apple IIe was
such a basic machine by today's standards, Bowen couldn't multi-task
on it. He could not do anything with the machine, such as check his
own mail, while a visitor was logged into PI.
Zen was a watershed in the Australian BBS community. Zen multi-tasked.
Up to four people could ring up and login to the machine at any one
time, and Bowen could do his own thing while his users were on-line.
Better still, his users could talk request each other instead of
hassling him all the time. Having users on a multi-tasking machine
with multiple phone lines was like having a gaggle of children. For
the most part, they amused each other.
Mainstream and respectful of authority on the surface, Bowen possessed
the same streak of anti-establishment views harboured by many in the
underground. His choice of name for Zen underlined this. Zen came from
the futuristic British TV science fiction series `Blake 7', in which a
bunch of underfunded rebels attempted to overthrow an evil
totalitarian government. Zen was the computer on the rebels' ship. The
rebels banded together after meeting on a prison ship; they were all
being transported to a penal settlement on another planet. It was a
story people in the Australian underground could relate to. One of the
lead characters, a sort of heroic anti-hero, had been sentenced to
prison for computer hacking. His big mistake, he told fellow rebels,
was that he had relied on other people. He trusted them. He should
have worked alone.
Craig Bowen had no idea of how true that sentiment would ring in a
matter of months.
Bowen's place was a hub of current and future lights in the computer
underground. The Wizard. The Force. Powerspike. Phoenix. Electron.
Nom. Prime Suspect. Mendax. Train Trax. Some, such as Prime Suspect,
merely passed through, occasionally stopping in to check out the
action and greet friends. Others, such as Nom, were part of the
close-knit PI family. Nom helped Bowen set up PI. Like many early
members of the underground, they met through AUSOM, an Apple users'
society in Melbourne. Bowen wanted to run ASCII Express, a program
which allowed people to transfer files between their own computers and
PI. But, as usual, he and everyone he knew only had a pirated copy of
the program. No manuals. So Nom and Bowen spent one weekend picking
apart the program by themselves. They were each at home, on their own
machines, with copies. They sat on the phone for hours working through
how the program worked. They wrote their own manual for other people
in the underground suffering under the same lack of documentation.
Then they got it up and running on PI.
Making your way into the various groups in a BBS such as PI or Zen had
benefits besides hacking information. If you wanted to drop your
mantle of anonymity, you could join a pre-packaged, close-knit circle
of friends. For example, one clique of PI people were fanatical
followers of the film The Blues Brothers. Every Friday night, this
group dressed up in Blues Brothers costumes of a dark suit, white
shirt, narrow tie, Rayban sunglasses and, of course, the snap-brimmed
hat. One couple brought their child, dressed as a mini-Blues Brother.
The group of Friday night regulars made their way at 11.30 to
Northcote's Valhalla Theatre (now the Westgarth). Its grand but
slightly tatty vintage atmosphere lent itself to this alternative
culture flourishing in late-night revelries. Leaping up on stage
mid-film, the PI groupies sent up the actors in key scenes. It was a
fun and, as importantly, a cheap evening. The Valhalla staff admitted
regulars who were dressed in appropriate costume for free. The only
thing the groupies had to pay for was drinks at the intermission.
Occasionally, Bowen arranged gatherings of other young PI and Zen
users. Usually, the group met in downtown Melbourne, sometimes at the
City Square. The group was mostly boys, but sometimes a few girls
would show up. Bowen's sister, who used the handle Syn, hung around a
bit. She went out with a few hackers from the BBS scene. And she
wasn't the only one. It was a tight group which interchanged
boyfriends and girlfriends with considerable regularity. The group
hung out in the City Square after watching a movie, usually a horror
film. Nightmare 2. House 3. Titles tended to be a noun followed by a
numeral. Once, for a bit of lively variation, they went bowling and
drove the other people at the alley nuts. After the early
entertainment, it was down to McDonald's for a cheap burger. They
joked and laughed and threw gherkins against the restaurant's wall.
This was followed by more hanging around on the stone steps of the
City Square before catching the last bus or train home.
The social sections of PI and Zen were more successful than the
technical ones, but the private hacking section was even more
successful than the others. The hacking section was hidden; would-be
members of the Melbourne underground knew there was something going
on, but they couldn't find out what is was.
Getting an invite to the private area required hacking skill or
information, and usually a recommendation to Bowen from someone who
was already inside. Within the Inner Sanctum, as the private hacking
area was called, people could comfortably share information such as
opinions of new computer products, techniques for hacking, details of
companies which had set up new sites to hack and the latest rumours on
what the law enforcement agencies were up to.
The Inner Sanctum was not, however, the only private room. Two hacking
groups, Elite and H.A.C.K., guarded entry to their yet more exclusive
back rooms. Even if you managed to get entry to the Inner Sanctum, you
might not even know that H.A.C.K. or Elite existed. You might know
there was a place even more selective than your area, but exactly how
many layers of the onion stood between you and the most exclusive
section was anyone's guess. Almost every hacker interviewed for this
book described a vague sense of being somehow outside the innermost
circle. They knew it was there, but wasn't sure just what it was.
Bowen fielded occasional phone calls on his voice line from wanna-be
hackers trying to pry open the door to the Inner Sanctum. `I want
access to your pirate system,' the voice would whine.
`What pirate system? Who told you my system was a pirate system?'
Bowen sussed out how much the caller knew, and who had told him. Then
he denied everything.
To avoid these requests, Bowen had tried to hide his address, real
name and phone number from most of the people who used his BBSes. But
he wasn't completely successful. He had been surprised by the sudden
appearance one day of Masked Avenger on his doorstep. How Masked
Avenger actually found his address was a mystery. The two had chatted
in a friendly fashion on-line, but Bowen didn't give out his details.
Nothing could have prepared him for the little kid in the big crash
helmet standing by his bike in front of Bowen's house. `Hi!' he
squeaked. `I'm the Masked Avenger!'
Masked Avenger—a boy perhaps fifteen years old—was quite resourceful
to have found out Bowen's details. Bowen invited him in and showed him
the system. They became friends. But after that incident, Bowen
decided to tighten security around his personal details even more. He
began, in his own words, `moving toward full anonymity'. He invented
the name Craig Bowen, and everyone in the underground came to know him
by that name or his handle, Thunderbird1. He even opened a false bank
account in the name of Bowen for the periodic voluntary donations
users sent into PI. It was never a lot of money, mostly $5 or $10,
because students don't tend to have much money. He ploughed it all
back into PI.
People had lots of reasons for wanting to get into the Inner Sanctum.
Some wanted free copies of the latest software, usually pirated games
from the US. Others wanted to share information and ideas about ways
to break into computers, often those owned by local universities.
Still others wanted to learn about how to manipulate the telephone
system.
The private areas functioned like a royal court, populated by
aristocrats and courtiers with varying seniority, loyalties and
rivalries. The areas involved an intricate social order and respect
was the name of the game. If you wanted admission, you had to walk a
delicate line between showing your superiors that you possessed enough
valuable hacking information to be elite and not showing them so much
they would brand you a blabbermouth. A perfect bargaining chip was an
old password for Melbourne University's dial-out.
The university's dial-out was a valuable thing. A hacker could ring up
the university's computer, login as `modem' and the machine would drop
him into a modem which let him dial out again. He could then dial
anywhere in the world, and the university would foot the phone bill.
In the late 1980s, before the days of cheap, accessible Internet
connections, the university dial-out meant a hacker could access
anything from an underground BBS in Germany to a US military system in
Panama. The password put the world at his fingertips.
A hacker aspiring to move into PI's Inner Sanctum wouldn't give out
the current dial-out password in the public discussion areas. Most
likely, if he was low in the pecking order, he wouldn't have such
precious information. Even if he had managed to stumble across the
current password somehow, it was risky giving it out publicly. Every
wanna-be and his dog would start messing around with the university's
modem account. The system administrator would wise up and change the
password and the hacker would quickly lose his own access to the
university account. Worse, he would lose access for other hackers—the
kind of hackers who ran H.A.C.K., Elite and the Inner Sanctum. They
would be really cross. Hackers hate it when passwords on accounts they
consider their own are changed without warning. Even if the password
wasn't changed, the aspiring hacker would look like a guy who couldn't
keep a good secret.
Posting an old password, however, was quite a different matter. The
information was next to useless, so the hacker wouldn't be giving much
away. But just showing he had access to that sort of information
suggested he was somehow in the know. Other hackers might think he had
had the password when it was still valid. More importantly, by showing
off a known, expired password, the hacker hinted that he might just
have the current password. Voila! Instant respect.
Positioning oneself to win an invite into the Inner Sanctum was a game
of strategy; titillate but never go all the way. After a while,
someone on the inside would probably notice you and put in a word with
Bowen. Then you would get an invitation.
If you were seriously ambitious and wanted to get past the first inner
layer, you then had to start performing for real. You couldn't hide
behind the excuse that the public area might be monitored by the
authorities or was full of idiots who might abuse valuable hacking
information.
The hackers in the most elite area would judge you on how much
information you provided about breaking into computer or phone
systems. They also looked at the accuracy of the information. It was
easy getting out-of-date login names and passwords for a student
account on Monash University's computer system. Posting a valid
account for the New Zealand forestry department's VMS system intrigued
the people who counted considerably more.
The Great Rite of Passage from boy to man in the computer underground
was Minerva. OTC, Australia's then government-owned Overseas
Telecommunications Commission,3 ran Minerva, a system of three Prime
mainframes in Sydney. For hackers such as Mendax, breaking into
Minerva was the test.
Back in early 1988, Mendax was just beginning to explore the world of
hacking. He had managed to break through the barrier from public to
private section of PI, but it wasn't enough. To be recognised as
up-and-coming talent by the aristocracy of hackers such as The Force
and The Wizard, a hacker had to spend time inside the Minerva system.
Mendax set to work on breaking
into it.
Minerva was special for a number of reasons. Although it was in
Sydney, the phone number to its entry computer, called an X.25 pad,
was a free call. At the time Mendax lived in Emerald, a country town
on the outskirts of Melbourne. A call to most Melbourne numbers
incurred a long-distance charge, thus ruling out options such as the
Melbourne University dial-out for breaking into international computer
systems.
Emerald was hardly Emerald City. For a clever sixteen-year-old boy,
the place was dead boring. Mendax lived there with his mother; Emerald
was merely a stopping point, one of dozens, as his mother shuttled her
child around the continent trying to escape from a psychopathic former
de facto. The house was an emergency refuge for families on the run.
It was safe and so, for a time, Mendax and his exhausted family
stopped to rest before tearing off again in search of a new place to
hide.
Sometimes Mendax went to school. Often he didn't. The school system
didn't hold much interest for him. It didn't feed his mind the way
Minerva would. They Sydney computer system was a far more interesting
place to muck around in than the rural high school.
Minerva was a Prime computer, and Primes were in. Force, one of the
more respected hackers in 1987-88 in the Australian computer
underground, specialised in Primos, the special operating system used
on Prime computers. He wrote his own programs—potent hacking tools
which provided current usernames and passwords—and made the systems
fashionable in the computer underground.
Prime computers were big and expensive and no hacker could afford one,
so being able to access the speed and computational grunt of a system
like Minerva was valuable for running a hacker's own programs. For
example, a network scanner, a program which gathered the addresses of
computers on the X.25 network which would be targets for future
hacking adventures, ate up computing resources. But a huge machine
like Minerva could handle that sort of program with ease. Minerva also
allowed users to connect to other computer systems on the X.25 network
around the world. Better still, Minerva had a BASIC interpreter on it.
This allowed people to write programs in the BASIC programming
language—by far the most popular language at the time—and make them
run on Minerva. You didn't have to be a Primos fanatic, like Force, to
write and execute a program on the OTC computer. Minerva suited Mendax
very well.
The OTC system had other benefits. Most major Australian corporations
had accounts on the system. Breaking into an account requires a
username and password; find the username and you have solved half the
equation. Minerva account names were easy picking. Each one was
composed of three letters followed by three numbers, a system which
could have been difficult to crack except for the choice of those
letters and numbers. The first three letters were almost always
obvious acronyms for the company. For example, the ANZ Bank had
accounts named ANZ001, ANZ002 and ANZ002. The numbers followed the
same pattern for most companies. BHP001. CRA001. NAB001. Even OTC007.
Anyone with the IQ of a desk lamp could guess at least a few account
names on Minerva. Passwords were a bit tougher to come by, but Mendax
had some ideas for that. He was going to have a crack at social
engineering. Social engineering means smooth-talking someone in a
position of power into doing something for you. It always involved a
ruse of some sort.
Mendax decided he would social engineer a password out of one of
Minerva's users. He had downloaded a partial list of Minerva users
another PI hacker had generously posted for those talented enough to
make use of it. This list was maybe two years old, and incomplete, but
it contained 30-odd pages of Minerva account usernames, company names,
addresses, contact names and telephone and fax numbers. Some of them
would probably still be valid.
Mendax had a deep voice for his age; it would have been impossible to
even contemplate social engineering without it. Cracking adolescent
male voices were the kiss of death for would-be social engineers. But
even though he had the voice, he didn't have the office or the Sydney
phone number if the intended victim wanted a number to call back on.
He found a way to solve the Sydney phone number by poking around until
he dug up a number with Sydney's 02 area code which was permanently
engaged. One down, one to go.
Next problem: generate some realistic office background noise. He
could hardly call a company posing as an OTC official to cajole a
password when the only background noise was birds tweeting in the
fresh country air.
No, he needed the same background buzz as a crowded office in downtown
Sydney. Mendex had a tape recorder, so he could pre-record the sound
of an office and play it as background when he called companies on the
Minerva list. The only hurdle was finding the appropriate office
noise. Not even the local post office would offer a believable noise
level. With none easily accessible, he decided to make his own audible
office clutter. It wouldn't be easy. With a single track on his
recording device, he couldn't dub in sounds on top of each other: he
had to make all the noises simultaneously.
First, he turned on the TV news, down very low, so it just hummed in
the background. Then he set up a long document to print on his
Commodore MPS 801 printer. He removed the cover from the noisy dot
matrix machine, to create just the right volume of clackity-clack in
the background. Still, he needed something more. Operators' voices
mumbling across a crowded floor. He could mumble quietly to himself,
but he soon discovered his verbal skills had not developed to the
point of being able to stand in the middle of the room talking about
nothing to himself for a quarter of an hour. So he fished out his
volume of Shakespeare and started reading aloud. Loud enough to hear
voices, but not so loud that the intended victim would be able to pick
Macbeth. OTC operators had keyboards, so he began tapping randomly on
his. Occasionally, for a little variation, he walked up to the tape
recorder and asked a question—and then promptly answered it in
another voice. He stomped noisily away from the recorder again, across
the room, and then silently dove back to the keyboard for more
keyboard typing and mumblings of Macbeth.
It was exhausting. He figured the tape had to run for at least fifteen
minutes uninterrupted. It wouldn't look very realistic if the office
buzz suddenly went dead for three seconds at a time in the places
where he paused the tape to rest.
The tapes took a number of attempts. He would be halfway through,
racing through line after line of Shakespeare, rap-tap-tapping on his
keyboard and asking himself questions in authoritative voices when the
paper jammed in his printer. Damn. He had to start all over again.
Finally, after a tiring hour of auditory schizophrenia, he had the
perfect tape of office hubbub.
Mendax pulled out his partial list of Minerva users and began working
through the 30-odd pages. It was discouraging.
`The number you have dialled is not connected. Please check the number
before dialling again.'
Next number.
`Sorry, he is in a meeting at the moment. Can I have him return your
call?' Ah, no thanks.
Another try.
`That person is no longer working with our company. Can I refer you to
someone else?' Uhm, not really.
And another try.
Finally, success.
Mendax reached one of the contact names for a company in Perth. Valid
number, valid company, valid contact name. He cleared his throat to
deepen his voice even further and began.
`This is John Keller, an operator from OTC Minerva in Sydney. One of
our D090 hard drives has crashed. We've pulled across the data on the
back-up tape and we believe we have all your correct information. But
some of it might have been corrupted in the accident and we would just
like to confirm your details. Also the back-up tape is two days old,
so we want to check your information is up to date so your service is
not interrupted. Let me just dig out your details …' Mendax shuffled
some papers around on the table top.
`Oh, dear. Yes. Let's check it,' the worried manager responded.
Mendax started reading all the information on the Minerva list
obtained from Pacific Island, except for one thing. He changed the fax
number slightly. It worked. The manager jumped right in.
`Oh, no. That's wrong. Our fax number is definitely wrong,' he said
and proceeded to give the correct number.
Mendax tried to sound concerned. `Hmm,' he told the manager. `We may
have bigger problems than we anticipated. Hmm.' He gave another
pregnant pause. Working up the courage to ask the Big Question.
It was hard to know who was sweating more, the fretting Perth manager,
tormented by the idea of loud staff complaints from all over the
company because the Minerva account was faulty, or the gangly kid
trying his hand at social engineering for the first time.
`Well,' Mendax began, trying to keep the sound of authority in his
voice. `Let's see. We have your account number, but we had better
check your password … what was it?' An arrow shot from the bow.
It hit the target. `Yes, it's L-U-R-C-H—full stop.'
Lurch? Uhuh. An Addams Family fan.
`Can you make sure everything is working? We don't want our service
interrupted.' The Perth manager sounded quite anxious.
Mendax tapped away on the keyboard randomly and then paused. `Well, it
looks like everything is working just fine now,' he quickly reassured
him. Just fine.
`Oh, that's a relief!' the Perth manager exclaimed. `Thank you for
that. Thank you. I just can't thank you enough for calling us!' More
gratitude.
Mendax had to extract himself. This was getting embarrassing.
`Yes, well I'd better go now. More customers to call.' That should
work. The Perth manager wanted a contact telephone number, as
expected, if something went wrong—so Mendax gave him the one which
was permanently busy.
`Thank you again for your courteous service!' Uhuh. Anytime.
Mendax hung up and tried the toll-free Minerva number. The password
worked. He couldn't believe how easy it was to get in.
He had a quick look around, following the pattern of most hackers
breaking into a new machine. First thing to do was to check the
electronic mail of the `borrowed' account. Email often contains
valuable information. One company manager might send another
information about other account names, password changes or even phone
numbers to modems at the company itself. Then it was off to check the
directories available for anyone to read on the main system—another
good source of information. Final stop: Minerva's bulletin board of
news. This included postings from the system operators about planned
downtime or other service issues. He didn't stay long. The first visit
was usually mostly a bit of reconnaissance work.
Minerva had many uses. Most important among these was the fact that
Minerva gave hackers an entry point into various X.25 networks. X.25
is a type of computer communications network, much like the Unix-based
Internet or the VMS-based DECNET. It has different commands and
protocols, but the principle of an extensive worldwide data
communications network is the same. There is, however, one important
difference. The targets for hackers on the X.25 networks are often far
more interesting. For example, most banks are on X.25. Indeed, X.25
underpins many aspects of the world's financial markets. A number of
countries' classified military computer sites only run on X.25. It is
considered by many people to be more secure than the Internet or any
DECNET system.
Minerva allowed incoming callers to pass into the X.25
network—something most Australian universities did not offer at the
time. And Minerva let Australian callers do this without incurring a
long-distance telephone charge.
In the early days of Minerva, the OTC operators didn't seem to care
much about the hackers, probably because it seemed impossible to get
rid of them. The OTC operators managed the OTC X.25 exchange, which
was like a telephone exchange for the X.25 data network. This exchange
was the data gateway for Minerva and other systems connected to that
data network.
Australia's early hackers had it easy, until Michael Rosenberg
arrived.
Rosenberg, known on-line simply as MichaelR, decided to clean up
Minerva. An engineering graduate from Queensland University, Michael
moved to Sydney when he joined OTC at age 21. He was about the same
age as the hackers he was chasing off his system. Rosenberg didn't
work as an OTC operator, he managed the software which ran on Minerva.
And he made life hell for people like Force. Closing up security
holes, quietly noting accounts used by hackers and then killing those
accounts, Rosenberg almost single-handedly stamped out much of the
hacker activity in OTC's Minerva.
Despite this, the hackers—`my hackers' as he termed the regulars—had
a grudging respect for Rosenberg. Unlike anyone else at OTC, he was
their technical equal and, in a world where technical prowess was the
currency, Rosenberg was a wealthy young man.
He wanted to catch the hackers, but he didn't want to see them go to
prison. They were an annoyance, and he just wanted them out of his
system. Any line trace, however, had to go through Telecom, which was
at that time a separate body from OTC. Telecom, Rosenberg was told,
was difficult about these things because of strict privacy laws. So,
for the most part, he was left to deal with the hackers on his own.
Rosenberg could not secure his system completely since OTC didn't
dictate passwords to their customers. Their customers were usually
more concerned about employees being able to remember passwords easily
than worrying about warding off wily hackers. The result: the
passwords on a number of Minerva accounts were easy pickings.
The hackers and OTC waged a war from 1988 to 1990, and it was fought
in many ways.
Sometimes an OTC operator would break into a hacker's on-line session
demanding to know who was really using the account. Sometimes the
operators sent insulting messages to the hackers—and the hackers gave
it right back to them. They broke into the hacker's session with `Oh,
you idiots are at it again'. The operators couldn't keep the hackers
out, but they had other ways of getting even.
Electron, a Melbourne hacker and rising star in the Australian
underground, had been logging into a system in Germany via OTC's X.25
link. Using a VMS machine, a sort of sister system to Minerva, he had
been playing a game called Empire on the Altos system, a popular
hang-out for hackers. It was his first attempt at Empire, a complex
war game of strategy which attracted players from around the world.
They each had less than one hour per day to conquer regions while
keeping production units at a strategic level. The Melbourne hacker
had spent weeks building his position. He was in second place.
Then, one day, he logged into the game via Minerva and the German
system, and he couldn't believe what he saw on the screen in front of
him. His regions, his position in the game, all of it—weeks of
work—had been wiped out. An OTC operator had used an X.25
packet-sniffer to monitor the hacker's login and capture his password to
Empire. Instead of trading the usual insults, the operator had waited
for the hacker to logoff and then had hacked into the game and destroyed
the hacker's position.
Electron was furious. He had been so proud of his position in his very
first game. Still, wreaking havoc on the Minerva system in retribution
was out of the question. Despite the fact that they wasted weeks of
his work, Electron had no desire to damage their system. He considered
himself lucky to be able to use it as long as he did.
The anti-establishment attitudes nurtured in BBSes such as PI and Zen
fed on a love of the new and untried. There was no bitterness, just a
desire to throw off the mantle of the old and dive into the new.
Camaraderie grew from the exhilarating sense that the youth in this
particular time and place were constantly on the edge of big
discoveries. People were calling up computers with their modems and
experimenting. What did this key sequence do? What about that tone?
What would happen if … It was the question which drove them to stay
up day and night, poking and prodding. These hackers didn't for the
most part do drugs. They didn't even drink that much, given their age.
All of that would have interfered with their burning desire to know,
would have dulled their sharp edge. The underground's
anti-establishment views were mostly directed at organisations which
seemed to block the way to the new frontier—organisations like
Telecom.
It was a powerful word. Say `Telecom' to a member of the computer
underground from that era and you will observe the most striking
reaction. Instant contempt sweeps across his face. There is a pause as
his lips curl into a noticeable sneer and he replies with complete
derision, `Telescum'. The underground hated Australia's national
telephone carrier with a passion equalled only to its love of
exploration. They felt that Telecom was backward and its staff had no
idea how to use their own telecommunications technology. Worst of all,
Telecom seemed to actively dislike BBSes.
Line noise interfered with one modem talking to another, and in the
eyes of the computer underground, Telecom was responsible for the line
noise. A hacker might be reading a message on PI, and there, in the
middle of some juicy technical titbit, would be a bit of crud—random
characters `2'28 v'1';D>nj4'—followed by the comment, `Line noise.
Damn Telescum! At their best as usual, I see'. Sometimes the line
noise was so bad it logged the hacker off, thus forcing him to spend
another 45 minutes attack dialling the BBS. The modems didn't have
error correction, and the faster the modem speed, the worse the impact
of line noise. Often it became a race to read mail and post messages
before Telecom's line noise logged the hacker off.
Rumours flew through the underground again and again that Telecom was
trying to bring in timed local calls. The volume of outrage was
deafening. The BBS community believed it really irked the national
carrier that people could spend an hour logged into a BBS for the cost
of one local phone call. Even more heinous, other rumours abounded
that Telecom had forced at least one BBS to limit each incoming call
to under half an hour. Hence Telecom's other nickname in the computer
underground: Teleprofit.
To the BBS community, Telecom's Protective Services Unit was the
enemy. They were the electronic police. The underground saw Protective
Services as `the enforcers'—an all-powerful government force which
could raid your house, tap your phone line and seize your computer
equipment at any time. The ultimate reason to hate Telecom.
There was such hatred of Telecom that people in the computer
underground routinely discussed ways of sabotaging the carrier. Some
people talked of sending 240 volts of electricity down the telephone
line—an act which would blow up bits of the telephone exchange along
with any line technicians who happened to be working on the cable at
the time. Telecom had protective fuses which stopped electrical surges
on the line, but BBS hackers had reportedly developed circuit plans
which would allow high-frequency voltages to bypass them. Other
members of the underground considered what sweet justice it would be
to set fire to all the cables outside a particular Telecom exchange
which had an easily accessible cable entrance duct.
It was against this backdrop that the underground began to shift into
phreaking. Phreaking is loosely defined as hacking the telephone
system. It is a very loose definition. Some people believe phreaking
includes stealing a credit card number and using it to make a
long-distance call for free. Purists shun this definition. To them,
using a stolen credit card is not phreaking, it is carding. They argue
that phreaking demands a reasonable level of technical skill and
involves manipulation of a telephone exchange. This manipulation may
manifest itself as using computers or electrical circuits to generate
special tones or modify the voltage of a phone line. The manipulation
changes how the telephone exchange views a particular telephone
line. The result: a free and hopefully untraceable call. The purist
hacker sees phreaking more as a way of eluding telephone traces than of
calling his or her friends around the world for free.
The first transition into phreaking and eventually carding happened
over a period of about six months in 1988. Early hackers on PI and Zen
relied primarily on dial-outs, like those at Melbourne University or
Telecom's Clayton office, to bounce around international computer
sites. They also used X.25 dial-outs in other countries—the US,
Sweden and Germany—to make another leap in their international
journeys.
Gradually, the people running these dial-out lines wised up. Dial-outs
started drying up. Passwords were changed. Facilities were cancelled.
But the hackers didn't want to give up access to overseas systems.
They'd had their first taste of international calling and they wanted
more. There was a big shiny electronic world to explore out there.
They began trying different methods of getting where they wanted to
go. And so the Melbourne underground moved into phreaking.
Phreakers swarmed to PABXes like bees to honey. A PABX, a private
automatic branch exchange, works like a mini-Telecom telephone
exchange. Using a PABX, the employee of a large company could dial
another employee in-house without incurring the cost of a local
telephone call. If the employee was, for example, staying in a hotel
out of town, the company might ask him to make all his calls through
the company's PABX to avoid paying extortionate hotel long-distance
rates. If the employee was in Brisbane on business, he could dial a
Brisbane number which might route him via the company's PABX to
Sydney. From there, he might dial out to Rome or London, and the
charge would be billed directly to the company. What worked for an
employee also worked for a phreaker.
A phreaker dialling into the PABX would generally need to either know
or guess the password allowing him to dial out again. Often, the
phreaker was greeted by an automated message asking for the employee's
telephone extension—which also served as the password. Well, that was
easy enough. The phreaker simply tried a series of numbers until he
found one which actually worked.
Occasionally, a PABX system didn't even have passwords. The managers
of the PABX figured that keeping the phone number secret was good
enough security. Sometimes phreakers made free calls out of PABXes
simply by exploited security flaws in a particular model or brand of
PABX. A series of specific key presses allowed the phreaker to get in
without knowing a password, an employee's name, or even the name of
the company for that matter.
As a fashionable pastime on BBSes, phreaking began to surpass hacking.
PI established a private phreaking section. For a while, it became
almost old hat to call yourself a hacker. Phreaking was forging the
path forward.
Somewhere in this transition, the Phreakers Five sprung to life. A
group of five hackers-turned-phreakers gathered in an exclusive group
on PI. Tales of their late-night podding adventures leaked into the
other areas of the BBS and made would-be phreakers green with
jealousy.
First, the phreakers would scout out a telephone pod—the grey steel,
rounded box perched nondescriptly on most streets. Ideally, the chosen
pod would be by a park or some other public area likely to be deserted
at night. Pods directly in front of suburban houses were a bit
risky—the house might contain a nosy little old lady with a penchant
for calling the local police if anything looked suspicious. And what
she would see, if she peered out from behind her lace curtains, was a
small tornado of action.
One of the five would leap from the van and open the pod with a key
begged, borrowed or stolen from a Telecom technician. The keys seemed
easy enough to obtain. The BBSes message boards were rife with gleeful
tales of valuable Telecom equipment, such as 500 metres of cable or a
pod key, procured off a visiting Telecom repairman either through
legitimate means or in exchange for a six-pack of beer.
The designated phreaker would poke inside the pod until he found
someone else's phone line. He'd strip back the cable, whack on a pair
of alligator clips and, if he wanted to make a voice call, run it to a
linesman's handset also borrowed, bought or stolen from Telecom. If he
wanted to call another computer instead of talking voice, he would
need to extend the phone line back to the phreakers' car. This is
where the 500 metres of Telecom cable came in handy. A long cable
meant the car, containing five anxious, whispering young men and a
veritable junkyard of equipment, would not have to sit next to the pod
for hours on end. That sort of scene might look a little suspicious to
a local resident out walking his or her dog late one night.
The phreaker ran the cable down the street and, if possible, around
the corner. He pulled it into the car and attached it to the waiting
computer modem. At least one of the five was proficient enough with
electronics hardware to have rigged up the computer and modem to the
car battery. The Phreaker's Five could now call any computer without
being traced or billed. The phone call charges would appear at the end
of a local resident's phone bill. Telecom did not itemise residential
telephone bills at the time. True, it was a major drama to zoom around
suburban streets in the middle of the night with computers, alligator
clips and battery adaptors in tow, but that didn't matter so much. In
fact, the thrill of such a cloak-and-dagger operation was as good as
the actual hacking itself. It was illicit. In the phreakers' own eyes,
it was clever. And therefore it was fun.
Craig Bowen didn't think much of the Phreakers Five's style of
phreaking. In fact, the whole growth of phreaking as a pastime
depressed him a bit. He believed it just didn't require the technical
skills of proper hacking. Hacking was, in his view, about the
exploration of a brave new world of computers. Phreaking was, well, a
bit beneath a good hacker. Somehow it demeaned the task at hand.
Still, he could see how in some cases it was necessary in order to
continue hacking. Most people in the underground developed some basic
skills in phreaking, though people like Bowen always viewed it more as
a means to an end—just a way of getting from computer A to computer
B, nothing more. Nonetheless, he allowed phreaking discussion areas in
the private sections of PI.
What he refused to allow was discussion areas around credit card
fraud. Carding was anathema to Bowen and he watched with alarm as some
members of the underground began to shift from phreaking into carding.
Like the transition into phreaking, the move into carding was a
logical progression. It occurred over a period of perhaps six months
in 1988 and was as obvious as a group of giggling schoolgirls.
Many phreakers saw it simply as another type of phreaking. In fact it
was a lot less hassle than manipulating some company's PABX. Instead,
you just call up an operator, give him some stranger's credit card
number to pay for the call, and you were on your way. Of course, the
credit cards had a broader range of uses than the PABXes. The advent
of carding meant you could telephone your friends in the US or UK and
have a long voice conference call with all of them
simultaneously—something which could be a lot tougher to arrange on a
PABX. There were other benefits. You could actually charge things with
that credit card. As in goods. Mail order goods.
One member of the underground who used the handle Ivan Trotsky,
allegedly ordered $50000 worth of goods, including a jet ski, from the
US on a stolen card, only to leave it sitting on the Australian docks.
The Customs guys don't tend to take stolen credit cards for duty
payments. In another instance, Trotsky was allegedly more successful.
A try-hard hacker who kept pictures of Karl Marx and Lenin taped to
the side of his computer terminal, Trotsky regularly spewed communist
doctrine across the underground. A self-contained paradox, he spent
his time attending Communist Party of Australia meetings and duck
shoots. According to one hacker, Trotsky's particular contribution to
the overthrow of the capitalist order was the arrangement of a
shipment of expensive modems from the US using stolen credit cards. He
was rumoured to have made a tidy profit by selling the modems in the
computer community for about $200 each. Apparently, being part of the
communist revolution gave him all sorts of ready-made
rationalisations. Membership has its advantages.
To Bowen, carding was little more than theft. Hacking may have been a
moral issue, but in early 1988 in Australia it was not yet much of a
legal one. Carding was by contrast both a moral and a legal issue.
Bowen recognised that some people viewed hacking as a type of
theft—stealing someone else's computer resources—but the argument
was ambiguous. What if no-one needed those resources at 2 a.m. on a
given night? It might be seen more as `borrowing' an under-used asset,
since the hacker had not permanently appropriated any property. Not so
for carding.
What made carding even less noble was that it required the technical
skill of a wind-up toy. Not only was it beneath most good hackers, it
attracted the wrong sort of people into the hacking scene. People who
had little or no respect for the early Australian underground's golden
rules of hacking: don't damage computer systems you break into
(including crashing them); don't change the information in those
systems (except for altering logs to cover your tracks); and share
information. For most early Australian hackers, visiting someone
else's system was a bit like visiting a national park. Leave it as you
find it.
While the cream seemed to rise to the top of the hacking hierarchy, it
was the scum that floated at the top of the carding community. Few
people in the underground typified this more completely than Blue
Thunder, who had been hanging around the outskirts of the Melbourne
underground since at least 1986. The senior hackers treated Blue
Blunder, as they sometimes called him, with great derision.
His entrance into the underground was as ignominious as that of a
debutante who, delicately descending the grand steps of the ballroom,
trips and tumbles head-first onto the dance floor. He picked a fight
with the grande doyenne of the Melbourne underground.
The Real Article occupied a special place in the underground. For
starters, The Real Article was a woman—perhaps the only female to
play a major role in the early Melbourne underground scene. Although
she didn't hack computers, she knew a lot about them. She ran The Real
Connection, a BBS frequented by many of the hackers who hung out on
PI. She wasn't somebody's sister wafting in and out of the picture in
search of a boyfriend. She was older. She was as good as married. She
had kids. She was a force to be reckoned with in the hacking
community.
Forthright and formidable, The Real Article commanded considerable
respect among the underground. A good indicator of this respect was the
fact that the members of H.A.C.K. had inducted her as an honorary member
of their exclusive club. Perhaps it was because she ran a popular
board. More likely it was because, for all their bluff and bluster, most
hackers were young men with the problems of young men.  Being older and
wiser, The Real Article knew how to lend a sympathetic ear to those
problems. As a woman and a non-hacker, she was removed from the jumble
of male ego hierarchical problems associated with confiding in a
peer. She served as a sort of mother to the embryonic hacking community,
but she was young enough to avoid the judgmental pitfalls most parents
fall into with children.
The Real Article and Blue Thunder went into partnership running a BBS
in early 1986. Blue Thunder, then a high-school student, was desperate
to run a board, so she let him co-sysop the system. At first the
partnership worked. Blue Thunder used to bring his high-school essays
over for her to proofread and correct. But a short time into the
partnership, it went sour. The Real Article didn't like Blue Thunder's
approach to running a BBS, which appeared to her to be get information
from other hackers and then dump them. The specific strategy seemed to
be: get hackers to logon and store their valuable information on the
BBS, steal that information and then lock them out of their own
account. By locking them out, he was able to steal all the glory; he
could then claim the hacking secrets were his own. It was, in her
opinion, not only unsustainable, but quite immoral. She parted ways
with Blue Thunder and excommunicated him from her BBS.
Not long after, The Real Article started getting harassing phone calls
at 4 in the morning. The calls were relentless. Four a.m. on the dot,
every night. The voice at the other end of the line was computer
synthesised. This was followed by a picture of a machine-gun, printed
out on a cheap dot matrix printer in Commodore ASCII, delivered in her
letterbox. There was a threatening message attached which read
something like, `If you want the kids to stay alive, get them out of
the house'.
After that came the brick through the window. It landed in the back of
her TV. Then she woke up one morning to find her phone line dead.
Someone had opened the Telecom well in the nature strip across the
road and cut out a metre of cable. It meant the phone lines for the
entire street were down.
The Real Article tended to rise above the petty games that whining
adolescent boys with bruised egos could play, but this was too much.
She called in Telecom Protective Services, who put a last party
release on her phone line to trace the early-morning harassing calls.
She suspected Blue Thunder was involved, but nothing was ever proved.
Finally, the calls stopped. She voiced her suspicions to others in the
computer underground. Whatever shred of reputation Blue Chunder, as he
then became known for a time, had was soon decimated.
Since his own technical contributions were seen by his fellow BBS
users as limited, Blue Thunder would likely have faded into obscurity,
condemned to spend the rest of his time in the underground jumping
around the ankles of the aristocratic hackers. But the birth of
carding arrived at a fortuitous moment for him and he got into carding
in a big way, so big in fact that he soon got busted.
People in the underground recognised him as a liability, both because
of what many hackers saw as his loose morals and because he was
boastful of his activities. One key hacker said, `He seemed to relish
the idea of getting caught. He told people he worked for a credit
union and that he stole lots of credit card numbers. He sold
information, such as accounts on systems, for financial gain.' In
partnership with a carder, he also allegedly sent a bouquet of flowers
to the police fraud squad—and paid for it with a stolen credit card
number.
On 31 August 1988, Blue Thunder faced 22 charges in the Melbourne
Magistrates Court, where he managed to get most of the charges dropped
or amalgamated. He only ended up pleading guilty to five counts,
including deception and theft. The Real Article sat in the back of the
courtroom watching the proceedings. Blue Thunder must have been pretty
worried about what kind of sentence the magistrate would hand down
because she said he approached her during the lunch break and asked if
she would appear as a character witness for the defence. She looked
him straight in the eye and said, `I think you would prefer it if I
didn't'. He landed 200 hours of community service and an order to pay
$706 in costs.
Craig Bowen didn't like where the part of the underground typified by
Blue Thunder was headed. In his view, Chunder and Trotsky stood out as
bad apples in an otherwise healthy group, and they signalled an
unpleasant shift towards selling information. This was perhaps the
greatest taboo. It was dirty. It was seedy. It was the realm of
criminals, not explorers. The Australian computer underground had
started to lose some of its fresh-faced innocence.
Somewhere in the midst of all this, a new player entered the Melbourne
underground. His name was Stuart Gill, from a company called
Hackwatch.
Bowen met Stuart through Kevin Fitzgerald, a well-known local hacker
commentator who founded the Chisholm Institute of Technology's
Computer Abuse Research Bureau, which later became the Australian
Computer Abuse Research Bureau. After seeing a newspaper article
quoting Fitzgerald, Craig decided to ring up the man many members of
the underground considered to be a hacker-catcher. Why not? There were
no federal laws in Australia against hacking, so Bowen didn't feel
that nervous about it. Besides, he wanted to meet the enemy. No-one
from the Australian underground had ever done it before, and Bowen
decided it was high time. He wanted to set the record straight with
Fitzgerald, to let him know what hackers were really on about. They
began to talk periodically on the phone.
Along the way, Bowen met Stuart Gill who said that he was working with
Fitzgerald.4 Before long, Gill began visiting PI. Eventually, Bowen
visited Gill in person at the Mount Martha home he shared with his
elderly aunt and uncle. Stuart had all sorts of computer equipment
hooked up there, and a great number of boxes of papers in the garage.
`Oh, hello there, Paul,' Gill's ancient-looking uncle said when he saw
the twosome. As soon as the old man had tottered off, Gill pulled
Bowen aside confidentially.
`Don't worry about old Eric,' he said. `He lost it in the war. Today
he thinks I'm Paul, tomorrow it will be someone else.'
Bowen nodded, understanding.
There were many strange things about Stuart Gill, all of which seemed
to have a rational explanation, yet that explanation somehow never
quite answered the question in full.
Aged in his late thirties, he was much older and far more worldly than
Craig Bowen. He had very, very pale skin—so pasty it looked as though
he had never sat in the sun in his life.
Gill drew Bowen into the complex web of his life. Soon he told the
young hacker that he wasn't just running Hackwatch, he was also
involved in intelligence work. For the Australian Federal Police. For
ASIO. For the National Crime Authority. For the Victoria Police's
Bureau of Criminal Intelligence (BCI). He showed Bowen some secret
computer files and documents, but he made him sign a special form
first—a legal-looking document demanding non-disclosure based on some
sort of official secrets act.
Bowen was impressed. Why wouldn't he be? Gill's cloak-and-dagger world
looked like the perfect boy's own adventure. Even bigger and better
than hacking. He was a little strange, but that was part of the
allure.
Like the time they took a trip to Sale together around Christmas 1988.
Gill told Bowen he had to get out of town for a few days—certain
undesirable people were after him. He didn't drive, so could Craig
help him out? Sure, no problem. They had shared an inexpensive motel
room in Sale, paid for by Gill.
Being so close to Christmas, Stuart told Craig he had brought him two
presents. Craig opened the first—a John Travolta fitness book. When
Craig opened the second gift, he was a little stunned. It was a red
G-string for men. Craig didn't have a girlfriend at the time—perhaps
Stuart was trying to help him get one.
`Oh, ah, thanks,' Craig said, a bit confused.
`Glad you like it,' Stuart said. `Go on. Try it on.'
`Try it on?' Craig was now very confused.
`Yeah, mate, you know, to see if it fits. That's all.'
`Oh, um, right.'
Craig hesitated. He didn't want to seem rude. It was a weird request,
but never having been given a G-string before, he didn't know the
normal protocol. After all, when someone gives you a jumper, it's
normal for them to ask you to try it on, then and there, to see if it
fits.
Craig tried it on. Quickly.
`Yes, seems to fit,' Stuart said matter of factly, then turned away.
Craig felt relieved. He changed back into his clothing.
That night, and on many others during their trips or during Craig's
overnight visits to Stuart's uncle's house, Craig lay in bed wondering
about his secretive new friend.
Stuart was definitely a little weird, but he seemed to like women so
Craig figured he couldn't be interested in Craig that way. Stuart
bragged that he had a very close relationship with a female newspaper
reporter, and he always seemed to be chatting up the girl at the video
store.
Craig tried not to read too much into Stuart's odd behaviour, for the
young man was willing to forgive his friend's eccentricities just to
be part of the action. Soon Stuart asked Craig for access to
PI—unrestricted access.
The idea made Craig uncomfortable, but Stuart was so persuasive. How
would he be able to continue his vital intelligence work without
access to Victoria's most important hacking board? Besides, Stuart
Gill of Hackwatch wasn't after innocent-faced hackers like Craig
Bowen. In fact, he would protect Bowen when the police came down on
everyone. What Stuart really wanted was the carders—the fraudsters.
Craig didn't want to protect people like that, did he?
Craig found it a little odd, as usual, that Stuart seemed to be after
the carders, yet he had chummed up with Ivan Trotsky. Still, there
were no doubt secrets Stuart couldn't reveal—things he wasn't allowed
to explain because of his intelligence work.
Craig agreed.
What Craig couldn't have known as he pondered Stuart Gill from the
safety of his boyish bedroom was exactly how much innocence the
underground was still to lose. If he had foreseen the next few
years—the police raids, the Ombudsman's investigation, the stream of
newspaper articles and the court cases—Craig Bowen would, at that
very moment, probably have reached over and turned off his beloved PI
and Zen forever.