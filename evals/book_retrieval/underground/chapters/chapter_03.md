# Chapter 3: The American Connection.

CHAPTER 3 — The American Connection.
US forces give the nod; It's a setback for your country.
— from `US Forces', 10, 9, 8, 7, 6, 5, 4, 3, 2, 1.
Force had a secret. The Parmaster wanted it.
Like most hackers, The Parmaster didn't just want the secret, he
needed it. He was in that peculiar state attained by real hackers
where they will do just about anything to obtain a certain piece of
information. He was obsessed.
Of course, it wasn't the first time The Parmaster craved a juicy piece
of information. Both he and Force knew all about infatuation. That's
how it worked with real hackers. They didn't just fancy a titbit here
and there. Once they knew information about a particular system was
available, that there was a hidden entrance, they chased it down
relentlessly. So that was exactly what Par was doing. Chasing Force
endlessly, until he got what he wanted.
It began innocently enough as idle conversation between two giants in
the computer underground in the first half of 1988. Force, the
well-known Australian hacker who ran the exclusive Realm BBS in
Melbourne, sat chatting with Par, the American master of X.25
networks, in Germany. Neither of them was physically in Germany, but
Altos was.
Altos Computer Systems in Hamburg ran a conference feature called
Altos Chat on one of its machines. You could call up from anywhere on
the X.25 data communications network, and the company's computer would
let you connect. Once connected, with a few brief keystrokes, the
German machine would drop you into a real-time, on-screen talk session
with anyone else who happened to be on-line. While the rest of the
company's computer system grunted and toiled with everyday labours,
this corner of the machine was reserved for live on-line chatting. For
free. It was like an early form of the Internet Relay Chat. The
company probably hadn't meant to become the world's most prestigious
hacker hang-out, but it soon ended up doing so.
Altos was the first significant international live chat channel, and
for most hackers it was an amazing thing. The good hackers had cruised
through lots of computer networks around the world. Sometimes they
bumped into one another on-line and exchanged the latest gossip.
Occasionally, they logged into overseas BBSes, where they posted
messages. But Altos was different. While underground BBSes had a
tendency to simply disappear one day, gone forever, Altos was always
there. It was live. Instantaneous communications with a dozen other
hackers from all sorts of exotic places. Italy. Canada. France.
England. Israel. The US. And all these people not only shared an
interest in computer networks but also a flagrant contempt for
authority of any type. Instant, real-time penpals—with attitude.
However, Altos was more exclusive than the average underground BBS.
Wanna-be hackers had trouble getting into it because of the way X.25
networks were billed. Some systems on the network took reverse-charge
connections—like a 1-800 number—and some, including Altos, didn't.
To get to Altos you needed a company's NUI (Network User Identifier),
which was like a calling card number for the X.25 network, used to
bill your time on-line. Or you had to have access to a system like
Minerva which automatically accepted billing for all the connections
made.
X.25 networks are different in various ways from the Internet, which
developed later. X.25 networks use different communication protocols
and, unlike the Internet at the user-level, they only use addresses
containing numbers not letters. Each packet of information travelling
over a data network needs to be encased in a particular type of
envelope. A `letter' sent across the X.25 network needs an X.25
`stamped' envelope, not an Internet `stamped' envelope.
The X.25 networks were controlled by a few very large players,
companies such as Telenet and Tymnet, while the modern Internet is, by
contrast, a fragmented collection of many small and medium-sized
sites.
Altos unified the international hacking world as nothing else had
done. In sharing information about their own countries' computers and
networks, hackers helped each other venture further and further
abroad. The Australians had gained quite a reputation on Altos. They
knew their stuff. More importantly, they possessed DEFCON, a program
which mapped out uncharted networks and scanned for accounts on
systems within them. Force wrote DEFCON based on a simple automatic
scanning program provided by his friend and mentor, Craig Bowen
(Thunderbird1).
Like the telephone system, the X.25 networks had a large number of
`phone numbers', called network user addresses (NUAs). Most were not
valid. They simply hadn't been assigned to anyone yet. To break into
computers on the network, you had to find them first, which meant
either hearing about a particular system from a fellow hacker or
scanning. Scanning—typing in one possible address after another—was
worse than looking for a needle in a haystack. 02624-589004-0004. Then
increasing the last digit by one on each attempt. 0005. 0006. 0007.
Until you hit a machine at the other end.
Back in 1987 or early 1988, Force had logged into Pacific Island for a
talk with Craig Bowen. Force bemoaned the tediousness of hand
scanning.
`Well, why the hell are you doing it manually?' Bowen responded. `You
should just use my program.' He then gave Force the source code for
his simple automated scanning program, along with instructions.
Force went through the program and decided it would serve as a good
launchpad for bigger things, but it had a major limitation. The
program could only handle one connection at a time, which meant it
could only scan one branch of a network at a time.
Less than three months later, Force had rewritten Bowen's program into
the far more powerful DEFCON, which became the jewel in the crown of
the Australian hackers' reputation. With DEFCON, a hacker could
automatically scan fifteen or twenty network addresses simultaneously.
He could command the computer to map out pieces of the Belgian,
British and Greek X.25 communications networks, looking for computers
hanging off the networks like buds at the tips of tree branches.
Conceptually, the difference was a little like using a basic PC, which
can only run one program at a time, as opposed to operating a more
sophisticated one where you can open many windows with different
programs running all at once. Even though you might only be working in
one window, say, writing a letter, the computer might be doing
calculations in a spreadsheet in another window in the background. You
can swap between
different functions, which are all running in the background
simultaneously.
While DEFCON was busy scanning, Force could do other things, such as
talk on Altos. He continued improving DEFCON, writing up to four more
versions of the program. Before long, DEFCON didn't just scan twenty
different connections at one time; it also automatically tried to
break into all the computers it found through those connections.
Though the program only tried basic default passwords, it had a fair
degree of success, since it could attack so many network addresses at
once. Further, new sites and mini-networks were being added so quickly
that security often fell by the wayside in the rush to join in. Since
the addresses were unpublished, companies often felt this obscurity
offered enough protection.
DEFCON produced lists of thousands of computer sites to raid. Force
would leave it scanning from a hacked Prime computer, and a day or two
later he would have an output file with 6000 addresses on different
networks. He perused the list and selected sites which caught his
attention. If his program had discovered an interesting address, he
would travel over the X.25 network to the site and then try to break
into the computer at that address. Alternatively, DEFCON might have
already successfully penetrated the machine using a default password,
in which case the address, account name and password would all be
waiting for Force in the log file. He could just walk right in.
Everyone on Altos wanted DEFCON, but Force refused to hand over the
program. No way was he going to have other hackers tearing up virgin
networks. Not even Erik Bloodaxe, one of the leaders of the most
prestigious American hacking group, Legion of Doom (LOD), got DEFCON
when he asked for it. Erik took his handle from the name of a Viking
king who ruled over the area now known as York, England. Although Erik
was on friendly terms with the Australian hackers, Force remained
adamant. He would not let the jewel out of his hands.
But on this fateful day in 1988, Par didn't want DEFCON. He wanted the
secret Force had just discovered, but held so very close to his chest.
And the Australian didn't want to give it to him.
Force was a meticulous hacker. His bedroom was remarkably tidy, for a
hacker's room. It had a polished, spartan quality. There were a few
well-placed pieces of minimalist furniture:
a black enamel metal single bed, a modern black bedside
table and a single picture on the wall—a photographic poster of
lightning, framed in glass. The largest piece of furniture was a
blue-grey desk with a return, upon which sat his computer, a printer
and an immaculate pile of print-outs. The bookcase, a tall modern
piece matching the rest of the furniture, contained an extensive
collection of fantasy fiction books, including what seemed to be
almost everything ever written by David Eddings. The lower shelves
housed assorted chemistry and programming books. A chemistry award
proudly jutted out from the shelf housing a few Dungeons and Dragons
books.
He kept his hacking notes in an orderly set of plastic folders, all
filed in the bottom of his bookcase. Each page of notes, neatly
printed and surrounded by small, tidy handwriting revealing updates
and minor corrections, had its own plastic cover to prevent smudges or
stains.
Force thought it was inefficient to hand out his DEFCON program and
have ten people scan the same network ten different times. It wasted
time and resources. Further, it was becoming harder to get access to
the main X.25 sites in Australia, like Minerva. Scanning was the type
of activity likely to draw the attention of a system admin and result
in the account being killed. The more people who scanned, the more
accounts would be killed, and the less access the Australian hackers
would have. So Force refused to hand over DEFCON to hackers outside
The Realm, which is one thing that made it such a powerful group.
Scanning with DEFCON meant using Netlink, a program which legitimate
users didn't often employ. In his hunt for hackers, an admin might
look for people running Netlink, or he might just examine which
systems a user was connecting to. For example, if a hacker connected
directly to Altos from Minerva without hopping through a respectable
midpoint, such as another corporate machine overseas, he could count
on the Minerva admins killing off the account.
DEFCON was revolutionary for its time, and difficult to reproduce. It
was written for Prime computers, and not many hackers knew how to
write programs for Primes. In fact, it was exceedingly difficult for
most hackers to learn programming of any sort for large, commercial
machines. Getting the system engineering manuals was tough work and
many of the large companies guarded their manuals almost as trade
secrets. Sure, if you bought a $100000 system, the company would give
you a few sets of operating manuals, but that was well beyond the
reach of a teenage hacker. In general, information was hoarded—by the
computer manufacturers, by the big companies which bought the systems,
by the system administrators and even by the universities.
Learning on-line was slow and almost as difficult. Most hackers used
300 or 1200 baud modems. Virtually all access to these big, expensive
machines was illegal. Every moment on-line was a risky proposition.
High schools never had these sorts of expensive machines. Although
many universities had systems, the administrators were usually miserly
with time on-line for students. In most cases, students only got
accounts on the big machines in their second year of computer science
studies. Even then, student accounts were invariably on the
university's oldest, clunkiest machine. And if you weren't a comp-sci
student, forget it. Indulging your intellectual curiosity in VMS
systems would never be anything more than a pipe dream.
Even if you did manage to overcome all the roadblocks and develop some
programming experience in VMS systems, for example, you might only be
able to access a small number of machines on any given network. The
X.25 networks connected a large number of machines which used very
different operating systems. Many, such as Primes, were not in the
least bit intuitive. So if you knew VMS and you hit a Prime machine,
well, that was pretty much it.
Unless, of course, you happened to belong to a clan of hackers like
The Realm. Then you could call up the BBS and post a message. `Hey, I
found a really cool Primos system at this address. Ran into problems
trying to figure the parameters of the Netlink command. Ideas anyone?'
And someone from your team would step forward to help.
In The Realm, Force tried to assemble a diverse group of Australia's
best hackers, each with a different area of expertise. And he happened
to be the resident expert in Prime computers.
Although Force wouldn't give DEFCON to anyone outside The Realm, he
wasn't unreasonable. If you weren't in the system but you had an
interesting network you wanted mapped, he would scan it for you. Force
referred to scans for network user addresses as `NUA sprints'. He
would give you a copy of the NUA sprint. While he was at it, he would
also keep a copy for The Realm. That was efficient. Force's pet
project was creating a database of systems and networks for The Realm,
so he simply added the new information to its database.
Force's great passion was mapping new networks, and new mini-networks
were being added to the main X.25 networks all the time. A large
corporation, such a BHP, might set up its own small-scale network
connecting its offices in Western Australia, Queensland, Victoria and
the United Kingdom. That mini-network might be attached to a
particular X.25 network, such as Austpac. Get into the Austpac network
and chances were you could get into any of the company's sites.
Exploration of all this uncharted territory consumed most of Force's
time. There was something cutting-edge, something truly adventurous
about finding a new network and carefully piecing together a picture
of what the expanding web looked like. He drew detailed pictures and
diagrams showing how a new part of the network connected to the rest.
Perhaps it appealed to his sense of order, or maybe he was just an
adventurer at heart. Whatever the underlying motivation, the maps
provided The Realm with yet another highly prized asset.
When he wasn't mapping networks, Force published Australia's first
underground hacking journal, Globetrotter. Widely read in the
international hacking community, Globetrotter reaffirmed Australian
hackers' pre-eminent position in the international underground.
But on this particular day, Par wasn't thinking about getting a copy
of Globetrotter or asking Force to scan a network for him. He was
thinking about that secret. Force's new secret. The secret Parmaster
desperately wanted.
Force had been using DEFCON to scan half a dozen networks while he
chatted to Par on Altos. He found an interesting connection from the
scan, so he went off to investigate it. When he connected to the
unknown computer, it started firing off strings of numbers at Force's
machine. Force sat at his desk and watched the characters rush by on
his screen.
It was very odd. He hadn't done anything. He hadn't sent any commands
to the mystery computer. He hadn't made the slightest attempt to break
into the machine. Yet here the thing was throwing streams of numbers.
What kind of computer was this? There might have been some sort of
header which would identify the computer, but it had zoomed by so fast
in the unexpected data dump that Force had missed it.
Force flipped over to his chat with Par on Altos. He didn't completely
trust Par, thinking the friendly American sailed a bit close to the
wind. But Par was an expert in X.25 networks and was bound to have
some clue about these numbers. Besides, if they turned out to be
something sensitive, Force didn't have to tell Par where he found
them.
`I've just found a bizarre address. It is one strange system. When I
connected, it just started shooting off numbers at me. Check these
out.'
Force didn't know what the numbers were, but Par sure did. `Those look
like credit cards,' he typed back.
`Oh.' Force went quiet.
Par thought the normally chatty Australian hacker seemed astonished.
After a short silence, the now curious Par nudged the conversation
forward. `I have a way I can check out whether they really are valid
cards,' he volunteered. `It'll take some time, but I should be able to
do it and get back to you.'
`Yes.' Force seemed hesitant. `OK.'
On the other side of the Pacific from Par, Force thought about this
turn of events. If they were valid credit cards, that was very cool.
Not because he intended to use them for credit card fraud in the way
Ivan Trotsky might have done. But Force could use them for making
long-distance phone calls to hack overseas. And the sheer number of
cards was astonishing. Thousand and thousands of them. Maybe 10000.
All he could think was, Shit! Free connections for the rest of my
life.
Hackers such as Force considered using cards to call overseas computer
systems a little distasteful, but certainly acceptable. The card owner
would never end up paying the bill anyway. The hackers figured that
Telecom, which they despised, would probably have to wear the cost in
the end, and that was fine by them. Using cards to hack was nothing
like ordering consumer goods. That was real credit card fraud. And
Force would never sully his hands with that sort of behaviour.
Force scrolled back over his capture of the numbers which had been
injected into his machine. After closer inspection, he saw there were
headers which appeared periodically through the list. One said,
`CitiSaudi'.
He checked the prefix of the mystery machine's network address again.
He knew from previous scans that it belonged to one of the world's
largest banks. Citibank.
The data dump continued for almost three hours. After that, the
Citibank machine seemed to go dead. Force saw nothing but a blank
screen, but he kept the connection open. There was no way he was going
to hang up from this conversation. He figured this had to be a freak
connection—that he accidentally connected to this machine somehow,
that it wasn't really at the address he had tried based on the DEFCON
scan of Citibank's network.
How else could it have happened? Surely Citibank wouldn't have a
computer full of credit cards which spilled its guts every time
someone rang up to say `hello'? There would be tonnes of security on a
machine like that. This machine didn't even have a password. It didn't
even need a special character command, like a secret handshake.
Freak connections happened now and then on X.25
networks. They had the same effect as a missed voice phone
connection. You dial a friend's number—and you dial it correctly—but
somehow the call gets screwed up in the tangle of wires and exchanges
and your call gets put through to another number entirely. Of course,
once something like that happens to an X.25 hacker, he immediately
tries to figure out what the hell is going on, to search every shred
of data from the machine looking for the system's real address.
Because it was an accident, he suspects he will never find the machine
again.
Force stayed home from school for two days to keep the connection
alive and to piece together how he landed on the doorstep of this
computer. During this time, the Citibank computer woke up a few times,
dumped a bit more information, and then went back to sleep. Keeping
the connection alive meant running a small risk of discovery by an
admin at his launch point, but the rewards in this case far exceeded
the risk.
It wasn't all that unusual for Force to skip school to hack. His
parents used to tell him, `You better stop it, or you'll have to wear
glasses one day'. Still, they didn't seem to worry too much, since
their son had always excelled in school without much effort. At the
start of his secondary school career he had tried to convince his
teachers he should skip year 9. Some objected. It was a hassle, but he
finally arranged it by quietly doing the coursework for year 9 while
he was in year 8.
After Force had finally disconnected from the CitiSaudi computer and
had a good sleep, he decided to check on whether he could reconnect to
the machine. At first, no-one answered, but when he tried a little
later, someone answered all right. And it was the same talkative
resident who answered the door the first time. Although it only seemed
to work at certain hours of the day, the Citibank network address was
the right one. He was in again.
As Force looked over the captures from his Citibank hack, he noticed
that the last section of the data dump didn't contain credit card
numbers like the first part. It had people's names—Middle Eastern
names—and a list of transactions. Dinner at a restaurant. A visit to
a brothel. All sorts of transactions. There was also a number which
looked like a credit limit, in come cases a very, very large limit,
for each person. A sheik and his wife appeared to have credit limits
of $1 million—each. Another name had a limit of $5 million.
There was something strange about the data, Force thought. It was not
structured in a way which suggested the Citibank machine was merely
transmitting data to another machine. It looked more like a text file
which was being dumped from a computer to a line printer.
Force sat back and considered his exquisite discovery. He decided this
was something he would share only with a very few close, trusted
friends from The Realm. He would tell Phoenix and perhaps one other
member, but no-one else.
As he looked through the data once more, Force began to feel a little
anxious. Citibank was a huge financial institution, dependent on the
complete confidence of its customers. The corporation would lose a lot
of face if news of Force's discovery got out. It might care enough to
really come after him. Then, with the sudden clarity of the lightning
strike photo which hung on his wall, a single thought filled his mind.
I am playing with fire.
`Where did you get those numbers?' Par asked Force next time they were
both on Altos.
Force hedged. Par leaped forward.
`I checked those numbers for you. They're valid,' he told Force. The
American was more than intrigued. He wanted that network address. It
was lust. Next stop, mystery machine. `So, what's the address?'
That was the one question Force didn't want to hear. He and Par had a
good relationship, sharing information comfortably if occasionally.
But that relationship only went so far. For all he knew, Par might
have a less than desirable use for the information. Force didn't know
if Par carded, but he felt sure Par had friends who might be into it.
So Force refused to tell Par where to find the mystery machine.
Par wasn't going to give up all that easily. Not that he would use the
cards for free cash, but, hey, the mystery machine seemed like a very
cool place to check out. There would be no peace for Force until Par
got what he wanted. Nothing is so tempting to a hacker as the faintest
whiff of information about a system he wants, and Par hounded Force
until the Australian hacker relented just a bit.
Finally Force told Par roughly where DEFCON had been scanning for
addresses when it stumbled upon the CitiSaudi machine. Force wasn't
handing over the street address, just the name of the suburb. DEFCON
had been accessing the Citibank network through Telenet, a large
American data network using X.25 communications protocols. The
sub-prefixes for the Citibank portion of the network were 223 and 224.
Par pestered Force some more for the rest of the numbers, but the
Australian had dug his heels in. Force was too careful a player, too
fastidious a hacker, to allow himself to get mixed up in the things
Par might get up to.
OK, thought the seventeen-year-old Par, I can do this without you. Par
estimated there were 20000 possible addresses on that network, any one
of which might be the home of the mystery machine. But he assumed the
machine would be in the low end of the network, since the lower
numbers were usually used first and the higher numbers were generally
saved for other, special network functions. His assumptions narrowed
the likely search field to about 2000 possible addresses.
Par began hand-scanning on the Citibank Global Telecommunications
Network (GTN) looking for the mystery machine. Using his knowledge of
the X.25 network, he picked a number to start with. He typed 22301,
22302, 22303. On and on, heading toward 22310000. Hour after hour,
slowly, laboriously, working his way through all the options, Par
scanned out a piece, or a range, within the network. When he got bored
with the 223 prefix, he tried out the 224 one for a bit of variety.
Bleary-eyed and exhausted after a long night at the computer, Par felt
like calling it quits. The sun had splashed through the windows of his
Salinas, California, apartment hours ago. His living room was a mess,
with empty, upturned beer cans circling his Apple IIe. Par gave up for
a while, caught some shut-eye. He had gone through the entire list of
possible addresses, knocking at all the doors, and nothing had
happened. But over the next few days he returned to scanning the
network again. He decided to be more methodical about it and do the
whole thing from scratch a second time.
He was part way through the second scan when it happened. Par's
computer connected to something. He sat up and peered toward the
screen. What was going on? He checked the address. He was sure he had
tried this one before and nothing had answered. Things were definitely
getting strange. He stared at his computer.
The screen was blank, with the cursor blinking silently at the top.
Now what? What had Force done to get the computer to sing its song?
Par tried pressing the control key and a few different letters.
Nothing. Maybe this wasn't the right address after all. He
disconnected from the machine and carefully wrote down the address,
determined to try it again later.
On his third attempt, he connected again but found the same irritating
blank screen. This time he went through the entire alphabet with the
control key.
Control L.
That was the magic keystroke. The one that made CitiSaudi give up its
mysterious cache. The one that gave Par an adrenalin rush, along with
thousands and thousands of cards. Instant cash, flooding his screen.
He turned on the screen capture so he could collect all the
information flowing past and analyse it later. Par had to keep feeding
his little Apple IIe more disks to store all the data coming in
through his 1200 baud modem.
It was magnificent. Par savoured the moment, thinking about how much
he was going to enjoy telling Force. It was going to be sweet. Hey,
Aussie, you aren't the only show in town. See ya in Citibank.
An hour or so later, when the CitiSaudi data dump had finally
finished, Par was stunned at what he found in his capture. These
weren't just any old cards. These were debit cards, and they were held
by very rich Arabs. These people just plopped a few million in a bank
account and linked a small, rectangular piece of plastic to that
account. Every charge came directly out of the bank balance. One guy
listed in the data dump bought a $330,000 Mercedes Benz in
Istanbul—on his card. Par couldn't imagine being able to throw down a
bit of plastic for that. Taking that plastic out for a spin around the
block would bring a whole new meaning to the expression, `Charge it!'
When someone wins the lottery, they often feel like sharing with their
friends. Which is exactly what Par did. First, he showed his
room-mates. They thought it was very cool. But not nearly so cool as
the half dozen hackers and phreakers who happened to be on the
telephone bridge Par frequented when the master of X.25 read off a
bunch of the cards.
Par was a popular guy after that day. Par was great, a sort of Robin
Hood of the underground. Soon, everyone wanted to talk to him. Hackers
in New York. Phreakers in Virginia. And the Secret Service in San
Francisco.
Par didn't mean to fall in love with Theorem. It was an accident, and
he couldn't have picked a worse girl to fall for. For starters, she
lived in Switzerland. She was 23 and he was only seventeen. She also
happened to be in a relationship—and that relationship was with
Electron, one of the best Australian hackers of the late 1980s. But
Par couldn't help himself. She was irresistible, even though he had
never met her in person. Theorem was different. She was smart and
funny, but refined, as a European woman can be.
They met on Altos in 1988.
Theorem didn't hack computers. She didn't need to, since she could
connect to Altos through her old university computer account. She had
first found Altos on 23 December 1986. She remembered the date for two
reasons. First, she was amazed
at the power of Altos—that she could have a live conversation on-line
with a dozen people in different countries at the same time. Altos was
a whole new world for her. Second, that was the day she met Electron.
Electron made Theorem laugh. His sardonic, irreverent humour hit a
chord with her. Traditional Swiss society could be stifling and
closed, but Electron was a breath of fresh air. Theorem was Swiss but
she didn't always fit the mould. She hated skiing. She was six feet
tall. She liked computers.
When they met on-line, the 21-year-old Theorem was at a crossroad in
her youth. She had spent a year and a half at university studying
mathematics. Unfortunately, the studies had not gone well. The truth
be told, her second year of university was in fact the first year all
over again. A classmate had introduced her to Altos on the
university's computers. Not long after she struck up a relationship
with Electron, she dropped out of uni all together and enrolled in a
secretarial course. After that, she found a secretarial job at a
financial institution.
Theorem and Electron talked on Altos for hours at a time. They talked
about everything—life, family, movies, parties—but not much about
what most people on Altos talked about—hacking. Eventually, Electron
gathered up the courage to ask Theorem for her voice telephone number.
She gave it to him happily and Electron called her at home in
Lausanne. They talked. And talked. And talked. Soon they were on the
telephone all the time.
Seventeen-year-old Electron had never had a girlfriend. None of the
girls in his middle-class high school would give him the time of day
when it came to romance. Yet here was this bright, vibrant girl—a
girl who studied maths—speaking to him intimately in a melting French
accent. Best of all, she genuinely liked him. A few words from his
lips could send her into silvery peals of laughter.
When the phone bill arrived, it was $1000. Electron surreptitiously
collected it and buried it at the bottom of a drawer in his bedroom.
When he told Theorem, she offered to help pay for it. A cheque for
$700 showed up not long after. It made the task of explaining
Telecom's reminder notice to his father much easier.
The romantic relationship progressed throughout 1987 and the first
half of 1988. Electron and Theorem exchanged love letters and tender
intimacies over 16000 kilometres of computer networks, but the
long-distance relationship had some bumpy periods. Like when she had
an affair over several months with Pengo. A well-known German hacker
with links to the German hacking group called the Chaos Computer Club,
Pengo was also a friend and mentor to Electron. Pengo was, however,
only a short train ride away from Theorem. She became friends with
Pengo on Altos and eventually visited him. Things progressed from
there.
Theorem was honest with Electron about the affair, but there was
something unspoken, something below the surface. Even after the affair
ended, Theorem was sweet on Pengo the way a girl remains fond of her
first love regardless of how many other men she has slept with since
then.
Electron felt hurt and angry, but he swallowed his pride and forgave
Theorem her dalliance. Eventually, Pengo disappeared from the scene.
Pengo had been involved with people who sold US military
secrets—taken from computers—to the KGB. Although his direct
involvement in the ongoing international computer espionage had been
limited, he began to worry about the risks. His real interest was in
hacking, not spying. The Russian connection simply enabled him to get
access to bigger and better computers. Beyond that, he felt no loyalty
to the Russians.
In the first half of 1988, he handed himself in to the German
authorities. Under West German law at the time, a citizen-spy who
surrendered himself before the state discovered the crime, and thus
averted more damage to the state, acquired immunity from prosecution.
Having already been busted in December 1986 for using a stolen NUI,
Pengo decided that turning himself in would be his best hope of taking
advantage of this legal largesse.
By the end of the year, things had become somewhat hairy for Pengo and
in March 1989 the twenty-year-old from Berlin was raided again, this
time with the four others involved in the spy ring. The story broke
and the media exposed Pengo's real name. He didn't know if he would
eventually be tried and convicted of something related to the
incident. Pengo had a few things on his mind other than the six-foot
Swiss girl.
With Pengo out of the way, the situation between Theorem and the
Australian hacker improved. Until Par came along.
Theorem and Par began innocently enough. Being one of only a few girls
in the international hacking and phreaking scene and, more
particularly, on Altos, she was treated differently. She had lots of
male friends on the German chat system, and the boys told her things
in confidence they would never tell each other. They sought out her
advice. She often felt like she wore many hats—mother, girlfriend,
psychiatrist—when she spoke with the boys on Altos.
Par had been having trouble with his on-line girlfriend, Nora, and
when he met Theorem he turned to her for a bit of support. He had
travelled from California to meet Nora in person in New York. But when
he arrived in the sweltering heat of a New York summer, without
warning, her conservative Chinese parents didn't take kindly to his
unannounced appearance. There were other frictions between Nora and
Par. The relationship had been fine on Altos and on the phone, but
things were just not clicking in person.
He already knew that virtual relationships, forged over an electronic
medium which denied the importance of physical chemistry, could
sometimes be disappointing.
Par used to hang out on a phone bridge with another Australian member
of The Realm, named Phoenix, and with a fun girl from southern
California. Tammi, a casual phreaker, had a great personality and a
hilarious sense of humour. During those endless hours chatting, she
and Phoenix seemed to be in the throes of a mutual crush. In the
phreaking underground, they were known as a bit of a virtual item. She
had even invited Phoenix to come visit her sometime. Then, one day,
for the fun of it, Tammi decided to visit Par in Monterey. Her
appearance was a shock.
Tammi had described herself to Phoenix as being a blue-eyed, blonde
California girl. Par knew that Phoenix visualised her as a
stereotypical bikini-clad, beach bunny from LA. His perception rested
on a foreigner's view of the southern California culture. The land of
milk and honey. The home of the Beach Boys and TV series like
`Charlie's Angels'.
When Tammi arrived, Par knew instantly that she and Phoenix would
never hit it off in person. Tammi did in fact have both blonde hair
and blue eyes. She had neglected to mention, however, that she weighed
about 300 pounds, had a rather homely face and a somewhat down-market
style. Par really liked Tammi, but he couldn't get the ugly phrase
`white trash' out of his thoughts. He pushed and shoved, but the
phrase was wedged in his mind. It fell to Par to tell Phoenix the
truth about Tammi.
So Par knew all about how reality could burst the foundations of a
virtual relationship.
Leaving New York and Nora behind, Par moved across the river to New
Jersey to stay with a friend, Byteman, who was one of a group of
hackers who specialised in breaking into computer systems run by Bell
Communications Research (Bellcore). Bellcore came into existence at
the beginning of 1984 as a result of the break-up of the US telephone
monopoly known as Bell Systems. Before the break-up, Bell Systems'
paternalistic holding company, American Telephone and Telegraph
(AT&T), had
fostered the best and brightest in Bell Labs, its research arm. Over
the course of its history, Bell Labs boasted at least seven
Nobel-prize winning researchers and numerous scientific achievements.
All of which made Bellcore a good target for hackers trying to prove
their prowess.
Byteman used to chat with Theorem on Altos, and eventually he called
her, voice. Par must have looked pretty inconsolable, because one day
while Byteman was talking to Theorem, he suddenly said to her, `Hey,
wanna talk to a friend of mine?' Theorem said `Sure' and Byteman
handed the telephone to Par. They talked for about twenty minutes.
After that they spoke regularly both on Altos and on the phone. For
weeks after Par returned to California, Theorem tried to cheer him up
after his unfortunate experience with Nora. By mid-1988, they had
fallen utterly and passionately in love.
Electron, an occasional member of Force's Realm group, took the news
very badly. Not everyone on Altos liked Electron. He could be a little
prickly, and very cutting when he chose to be, but he was an ace
hacker, on an international scale, and everyone listened to him.
Obsessive, creative and quick off the mark, Electron had respect,
which is one reason Par felt so badly.
When Theorem told Electron the bad news in a private conversation
on-line, Electron had let fly in the public area, ripping into the
American hacker on the main chat section of Altos, in front of
everyone.
Par took it on the chin and refused to fight back. What else could he
do? He knew what it was like to hurt. He felt for the guy and knew how
he would feel if he lost Theorem. And he knew that Electron must be
suffering a terrible loss of face. Everyone saw Electron and Theorem
as an item. They had been together for more than a year. So Par met
Electron's fury with grace and quiet words of consolation.
Par didn't hear much from Electron after that day. The Australian
still visited Altos, but he seemed more withdrawn, at least whenever
Par was around. After that day, Par ran into him once, on a phone
bridge with a bunch of Australian hackers.
Phoenix said on the bridge, `Hey, Electron. Par's on the bridge.'
Electron paused. `Oh, really,' he answered coolly. Then he went
silent.
Par let Electron keep his distance. After all, Par had what really
counted—the girl.
Par called Theorem almost every day. Soon they began to make plans for
her to fly to California so they could meet in person. Par tried not
to expect too much, but he found it difficult to stop savouring the
thought of finally seeing Theorem face to face. It gave him
butterflies.
Yeah, Par thought, things are really looking up.
The beauty of Altos was that, like Pacific Island or any other local
BBS, a hacker could take on any identity he wanted. And he could do it
on an international scale. Visiting Altos was like attending a
glittering masquerade ball. Anyone could recreate himself. A socially
inept hacker could pose as a character of romance and adventure. And a
security official could pose as a hacker.
Which is exactly what Telenet security officer Steve Mathews did on 27
October 1988. Par happened to be on-line, chatting away with his
friends and hacker colleagues. At any given moment, there were always
a few strays on Altos, a few people who weren't regulars. Naturally,
Mathews didn't announce himself as being a Telenet guy. He just
slipped quietly onto Altos looking like any other hacker. He might
engage a hacker in conversation, but he let the hacker do most of the
talking. He was there to listen.
On that fateful day, Par happened to be in one of his magnanimous
moods. Par had never had much money growing up, but he was always very
generous with what he did have. He talked for a little while with the
unknown hacker on Altos, and then gave him one of the debit cards
taken from his visits to the CitiSaudi computer. Why not? On Altos, it
was a bit like handing out your business card. `The
Parmaster—Parameters Par Excellence'.
Par had got his full name—The Parmaster—in his earliest hacking
days. Back then, he belonged to a group of teenagers involved in
breaking the copy protections on software programs for Apple IIes,
particularly games. Par had a special gift for working out the copy
protection parameters, which was a first step in bypassing the
manufacturers' protection schemes. The ringleader of the group began
calling him `the master of parameters'—The Parmaster—Par, for short.
As he moved into serious hacking and developed his expertise in X.25
networks, he kept the name because it fitted nicely in his new
environment. `Par?' was a common command on an X.25 pad, the modem
gateway to an X.25 network.
`I've got lots more where that come from,' Par told the stranger on
Altos. `I've got like 4000 cards from a Citibank system.'
Not long after that, Steve Mathews was monitoring Altos again, when
Par showed up handing out cards to people once more.
`I've got an inside contact,' Par confided. `He's gonna make up a
whole mess of new, plastic cards with all these valid numbers from the
Citibank machine. Only the really big accounts, though. Nothing with a
balance under $25000.'
Was Par just making idle conversation, talking big on Altos? Or would
he really have gone through with committing such a major fraud?
Citibank, Telenet and the US Secret Service would never know, because
their security guys began closing the net around Par before he had a
chance to take his idea any further.
Mathews contacted Larry Wallace, fraud investigator with Citibank in
San Mateo, California. Wallace checked out the cards. They were valid
all right. They belonged to the Saudi-American Bank in Saudi Arabia
and were held on a Citibank database in Sioux Falls, South Dakota.
Wallace determined that, with its affiliation to the Middle Eastern
bank, Citibank had a custodial responsibility for the accounts. That
meant he could open a major investigation.
On 7 November, Wallace brought in the US Secret Service. Four days
later, Wallace and Special Agent Thomas Holman got their first major
lead when they interviewed Gerry Lyons of Pacific Bell's security
office in San Francisco.
Yes, Lyons told the investigators, she had some information they might
find valuable. She knew all about hackers and phreakers. In fact, the
San Jose Police had just busted two guys trying to phreak at a pay
phone. The phreakers seemed to know something about a Citibank system.
When the agents showed up at the San Jose Police Department for their
appointment with Sergeant Dave Flory, they received another pleasant
surprise. The sergeant had a book filled with hackers' names and
numbers seized during the arrest of the two pay-phone phreakers. He
also happened to be in possession of a tape recording of the phreakers
talking to Par from a prison phone.
The cheeky phreakers had used the prison pay phone to call up a
telephone bridge located at the University of Virginia. Par, the
Australian hackers and other assorted American phreakers and hackers
visited the bridge frequently. At any one moment, there might be eight
to ten people from the underground sitting on the bridge. The
phreakers found Par hanging out there, as usual, and they warned him.
His name and number were inside the book seized by police when they
were busted.
Par didn't seem worried at all.
`Hey, don't worry. It's cool,' he reassured them. `I have just
disconnected my phone number today—with no forwarding details.'
Which wasn't quite true. His room-mate, Scott, had indeed disconnected
the phone which was in his name because he had been getting prank
calls. However, Scott opened a new telephone account at the same
address with the same name on the same day—all of which made the job
of tracking down the mysterious hacker named Par much easier for the
law enforcement agencies.
In the meantime, Larry Wallace had been ringing around his contacts in
the security business and had come up with another lead. Wanda Gamble,
supervisor for the Southeastern Region of MCI Investigations, in
Atlanta, had a wealth of information on the hacker who called himself
Par. She was well connected when it came to hackers, having acquired a
collection of reliable informants during her investigations of
hacker-related incidents. She gave the Citibank investigator two
mailbox numbers for Par. She also handed them what she believed was
his home phone number.
The number checked out and on 25 November, the day after Thanksgiving,
the Secret Service raided Par's house. The raid was terrifying. At
least four law enforcement officers burst through the door with guns
drawn and pointed. One of them had a shotgun. As is often the case in
the US, investigators from private, commercial organisations—in this
case Citibank and Pacific Bell—also took part in the raid.
The agents tore the place apart looking for evidence. They dragged
down the food from the kitchen cupboards. They emptied the box of
cornflakes into the sink looking for hidden computer disks. They
looked everywhere, even finding a ceiling cavity at the back of a
closet which no-one even knew existed.
They confiscated Par's Apple IIe, printer and modem. But, just to be
sure, they also took the Yellow Pages, along with the telephone and
the new Nintendo game paddles Scott had just bought. They scooped up
the very large number of papers which had been piled under the coffee
table, including the spiral notebook with Scott's airline bookings
from his job as a travel agent. They even took the garbage.
It wasn't long before they found the red shoebox full of disks peeping
out from under the fish tank next to Par's computer.
They found lots of evidence. What they didn't find was Par.
Instead, they found Scott and Ed, two friends of Par. They were pretty
shaken up by the raid. Not knowing Par's real identity, the Secret
Service agents accused Scott of being Par. The phone was in his name,
and Special Agent Holman had even conducted some surveillance more
than a week before the raid, running the plates on Scott's 1965 black
Ford Mustang parked in front of the house. The Secret Service was sure
it had its man, and Scott had a hell of a time convincing them
otherwise.
Both Scott and Ed swore up and down that they weren't hackers or
phreakers, and they certainly weren't Par. But they knew who Par was,
and they told the agents his real name. After considerable pressure
from the Secret Service, Scott and Ed agreed to make statements down
at the police station.
In Chicago, more than 2700 kilometres away from the crisis unfolding
in northern California, Par and his mother watched his aunt walk down
the aisle in her white gown.
Par telephoned home once, to Scott, to say `hi' from the Midwest. The
call came after the raid.
`So,' a relaxed Par asked his room-mate, `How are things going at
home?'
`Fine,' Scott replied. `Nothing much happening here.'
Par looked down at the red bag he was carrying with a momentary
expression of horror. He realised he stood out in the San Jose bus
terminal like a peacock among the pigeons …
Blissfully ignorant of the raid which had occurred three days before,
Par and his mother had flown into San Jose airport. They had gone to
the bus terminal to pick up a Greyhound home to the Monterey area.
While waiting for the bus, Par called his friend Tammi to say he was
back in California.
Any casual bystander waiting to use the pay phones at that moment
would have seen a remarkable transformation in the brown-haired boy at
the row of phones. The smiling face suddenly dropped in a spasm of
shock. His skin turned ash white as the blood fled south. His deep-set
chocolate brown eyes, with their long, graceful lashes curving upward
and their soft, shy expression, seemed impossibly large.
For at that moment Tammi told Par that his house had been raided by
the Secret Service. That Scott and Ed had been pretty upset about
having guns shoved in their faces, and had made statements about him
to the police. That they thought their phone was tapped. That the
Secret Service guys were still hunting for Par, they knew his real
name, and she thought there was an all points bulletin out for him.
Scott had told the Secret Service about Par's red bag, the one with
all his hacking notes that he always carried around. The one with the
print-out of all the Citibank credit card numbers.
And so it was that Par came to gaze down at his bag with a look of
alarm. He realised instantly that the Secret Service would be looking
for that red bag. If they didn't know what he looked like, they would
simply watch for the bag.
That bag was not something Par could hide easily. The Citibank
print-out was the size of a phone book. He also had dozens of disks
loaded with the cards and other sensitive hacking information.
Par had used the cards to make a few free calls, but he hadn't been
charging up any jet skis. He fought temptation valiantly, and in the
end he had won, but others might not have been so victorious in the
same battle. Par figured that some less scrupulous hackers had
probably been charging up a storm. He was right. Someone had, for
example, tried to send a $367 bouquet of flowers to a woman in El Paso
using one of the stolen cards. The carder had unwittingly chosen a
debit card belonging to a senior Saudi bank executive who happened to
be in his office at the time the flower order was placed. Citibank
investigator Larry Wallace added notes on that incident to his growing
file.
Par figured that Citibank would probably try to pin every single
attempt at carding on him. Why not? What kind of credibility would a
seventeen-year-old hacker have in denying those sorts of allegations?
Zero. Par made a snap decision. He sidled up to a trash bin in a dark
corner. Scanning the scene warily, Par casually reached into the red
bag, pulled out the thick wad of Citibank card print-outs and stuffed
it into the bin. He fluffed a few stray pieces of garbage over the
top.
He worried about the computer disks with all his other valuable
hacking information. They represented thousands of hours of work and
he couldn't bring himself to throw it all away. The 10 megabyte
trophy. More than 4000 cards. 130000 different transactions. In the
end, he decided to hold on to the disks, regardless of the risk. At
least, without the print-out, he could crumple the bag up a bit and
make it a little less conspicuous. As Par slowly moved away from the
bin, he glanced back to check how nondescript the burial site appeared
from a distance. It looked like a pile of garbage. Trash worth
millions of dollars, headed for the dump.
As he boarded the bus to Salinas with his mother, Par's mind was
instantly flooded with images of a homeless person fishing the
print-out from the bin and asking someone about it. He tried to push
the idea from his head.
During the bus ride, Par attempted to figure out what he was going to
do. He didn't tell his mother anything. She couldn't even begin to
comprehend his world of computers and networks, let alone his current
predicament. Further, Par and his mother had suffered from a somewhat
strained relationship since he ran away from home not long after his
seventeenth birthday. He had been kicked out of school for
non-attendance, but had found a job tutoring students in computers at
the local college. Before the trip to Chicago, he had seen her just
once in six months. No, he couldn't turn to her for help.
The bus rolled toward the Salinas station. En route, it travelled down
the street where Par lived. He saw a jogger, a thin black man wearing
a walkman. What the hell is a jogger doing here, Par thought. No-one
jogged in the semi-industrial neighbourhood. Par's house was about the
only residence amid all the light-industrial buildings. As soon as the
jogger was out of sight of the house, he suddenly broke away from his
path, turned off to one side and hit the ground. As he lay on his
stomach on some grass, facing the house, he seemed to begin talking
into the walkman.
Sitting watching this on the bus, Par flipped out. They were out to
get him, no doubt about it. When the bus finally arrived at the depot
and his mother began sorting out their luggage, Par tucked the red bag
under his arm and disappeared. He found a pay phone and called Scott
to find out the status of things. Scott handed the phone to Chris,
another friend who lived in the house. Chris had been away at his
parents' home during the Thanksgiving raid.
`Hold tight and lay low,' Chris told Par.
`I'm on my way over to pick you up and take you to a lawyer's office
where you can get some sort of protection.'
A specialist in criminal law, Richard Rosen was born in New York but
raised in his later childhood in California. He had a personality
which reflected the steely stubbornness of a New Yorker, tempered with
the laid-back friendliness of the west coast. Rosen also harboured a
strong anti-authoritarian streak. He represented the local chapter of
Hell's Angels in the middle-class County of Monterey. He also caused a
splash representing the growing midwifery movement, which promoted
home-births. The doctors of California didn't like him much as a
result.
Par's room-mates met with Rosen after the raid to set things up for
Par's return. They told him about the terrifying ordeal of the Secret
Service raid, and how they were interrogated for an hour and a half
before being pressured to give statements. Scott, in particular, felt
that he had been forced to give a statement against Par under duress.
While Par talked to Chris on the phone, he noticed a man standing at
the end of the row of pay phones. This man was also wearing a walkman.
He didn't look Par in the eye. Instead, he faced the wall, glancing
furtively off to the side toward where Par was standing. Who was that
guy? Fear welled up inside Par and all sorts of doubts flooded his
mind. Who could he trust?
Scott hadn't told him about the raid. Were his room-mates in cahoots
the Secret Service? Were they just buying time so they could turn him
in? There was no-one else Par could turn to. His mother wouldn't
understand. Besides, she had problems of her own. And he didn't have a
father. As far as Par was concerned, his father was as good as dead.
He had never met the man, but he heard he was a prison officer in
Florida. Not a likely candidate for helping Par in this situation. He
was close to his grandparents—they had bought his computer for him as
a present—but they lived in a tiny Mid-Western town and they simply
wouldn't understand either.
Par didn't know what to do, but he didn't seem to have many options at
the moment, so he told Chris he would wait at the station for him.
Then he ducked around a corner and tried to hide.
A few minutes later, Chris pulled into the depot. Par dove into the
Toyota Landcruiser and Chris tore out of the station toward Rosen's
office. They noticed a white car race out of the bus station after
them.
While they drove, Par pieced together the story from Chris. No-one had
warned him about the raid because everyone in the house believed the
phone line was tapped. Telling Par while he was in Chicago might have
meant another visit from the Secret Service. All they had been able to
do was line up Rosen to help him.
Par checked the rear-view mirror. The white car was still following
them. Chris made a hard turn at the next intersection and accelerated
down the California speedway. The white car tore around the corner in
pursuit. No matter what Chris did, he couldn't shake the tail. Par sat
in the seat next to Chris, quietly freaking out.
Just 24 hours before, he had been safe and sound in Chicago. How did
he end up back here in California being chased by a mysterious driver
in a white car?
Chris tried his best to break free, swerving and racing. The white car
wouldn't budge. But Chris and Par had one advantage over the white
car; they were in a four-wheel drive. In a split-second decision,
Chris jerked the steering wheel to one side. The Landcruiser veered
off the road onto a lettuce field. Par gripped the inside of the door
as the 4WD bounced through the dirt over the neat crop rows. Near-ripe
heads of lettuce went flying out from under the tires. Half-shredded
lettuce leaves filled the air. A cloud of dirt enveloped the car. The
vehicle skidded and jerked, but finally made its way to a highway at
the far end of the field. Chris hit the highway running, swerving into
the lane at high speed.
When Par looked back, the white car had disappeared. Chris kept his
foot on the accelerator and Par barely breathed until the Landcruiser
pulled up in front of Richard Rosen's building.
Par leaped out, the red bag still clutched tightly under his arm, and
high-tailed it into the lawyer's office. The receptionist looked a bit
shocked when he said his name. Someone must have filled her in on the
details.
Rosen quickly ushered him into his office. Introductions were brief
and Par cut to the story of the chase. Rosen listened intently,
occasionally asking a well-pointed question, and then took control of
the situation.
The first thing they needed to do was call off the Secret Service
chase, Rosen said, so Par didn't have to spend any more time ducking
around corners and hiding in bus depots. He called the Secret
Service's San Francisco office and asked Special Agent Thomas J.
Holman to kill the Secret Service pursuit in exchange for an agreement
that Par would turn himself in to be formally charged.
Holman insisted that they had to talk to Par.
No, Rosen said. There would be no interviews for Par by law
enforcement agents until a deal had been worked out.
But the Secret Service needed to talk to Par, Holman insisted. They
could only discuss all the other matters after the Secret Service had
had a chance to talk with Par.
Rosen politely warned Holman not to attempt to contact his client. You
have something to say to Par, you go through me, he said. Holman did
not like that at all. When the Secret Service wanted to talk to
someone, they were used to getting their way. He pushed Rosen, but the
answer was still no. No no no and no again. Holman had made a mistake.
He had assumed that everyone wanted to do business with the United
States Secret Service.
When he finally realised Rosen wouldn't budge, Holman gave up. Rosen
then negotiated with the federal prosecutor, US Attorney Joe Burton,
who was effectively Holman's boss in the case, to call off the pursuit
in exchange for Par handing himself in to be formally charged.
Then Par gave Rosen his red bag, for safekeeping.
At about the same time, Citibank investigator Wallace and Detective
Porter of the Salinas Police interviewed Par's mother as she returned
home from the bus depot. She said that her son had moved out of her
home some six months before, leaving her with a $2000 phone bill she
couldn't pay. They asked if they could search her home. Privately, she
worried about what would happen if she refused. Would they tell the
office where she worked as a clerk? Could they get her fired? A simple
woman who had little experience dealing with law enforcement agents,
Par's mother agreed. The investigators took Par's disks and papers.
Par turned himself in to the Salinas Police in the early afternoon of
12 December. The police photographed and fingerprinted him before
handing him a citation—a small yellow slip headed `502 (c) (1) PC'.
It looked like a traffic ticket, but the two charges Par faced were
felonies, and each carried a maximum term of three years for a minor.
Count 1, for hacking into Citicorp Credit Services, also carried a
fine of up to $10000. Count 2, for `defrauding a telephone service',
had no fine: the charges were for a continuing course of conduct,
meaning that they applied to the same activity over an extended period
of time.
Federal investigators had been astonished to find Par was so young.
Dealing with a minor in the federal court system was a big hassle, so
the prosecutor decided to ask the state authorities to prosecute the
case. Par was ordered to appear in Monterey County Juvenile Court on
10 July 1989.
Over the next few months, Par worked closely with Rosen. Though Rosen
was a very adept lawyer, the situation looked pretty depressing.
Citibank claimed it had spent $30000 on securing its systems and Par
believed that the corporation might be looking for up to $3 million in
total damages. While they couldn't prove Par had made any money from
the cards himself, the prosecution would argue that his generous
distribution of them had led to serious financial losses. And that was
just the financial institutions.
Much more worrying was what might come out about Par's visits to TRW's
computers. The Secret Service had seized at least one disk with TRW
material on it.
TRW was a large, diverse company, with assets of $2.1 billion and
sales of almost $7 billion in 1989, nearly half of which came from the
US government. It employed more than 73000 people, many of who worked
with the company's credit ratings business. TRW's vast databases held
private details of millions of people—addresses, phone numbers,
financial data.
That, however, was just one of the company's many businesses. TRW also
did defence work—very secret defence work. Its Space and Defense
division, based in Redondo Beach, California, was widely believed to
be a major beneficiary of the Reagan Government's Star Wars budget.
More than 10 per cent of the company's employees worked in this
division, designing spacecraft systems, communications systems,
satellites and other, unspecified, space `instruments'.
The siezed disk had some mail from the company's TRWMAIL systems. It
wasn't particularly sensitive, mostly just company propaganda sent to
employees, but the Secret Service might think that where there was
smoke, there was bound to be fire. TRW did the kind of work that makes
governments very nervous when it comes to unauthorised access. And Par
had visited certain TRW machines; he knew that company had a missiles
research section, and even a space weapons section.
With so many people out to get him—Citibank, the Secret Service, the
local police, even his own mother had helped the other side—it was
only a matter of time before they unearthed the really secret things
he had seen while hacking. Par began to wonder if was such a good idea
for him to stay around for the trial.
In early 1989, when Theorem stepped off the plane which carried her
from Switzerland to San Francisco, she was pleased that she had
managed to keep a promise to herself. It wasn't always an easy
promise. There were times of intimacy, of perfect connection, between
the two voices on opposite sides of the globe, when it seemed so
breakable.
Meanwhile, Par braced himself. Theorem had described herself in such
disparaging terms. He had even heard from others on Altos that she was
homely. But that description had ultimately come from her anyway, so
it didn't really count.
Finally, as he watched the stream of passengers snake out to the
waiting area, he told himself it didn't matter anyway. After all, he
had fallen in love with her—her being, her essence—not her image as
it appeared in flesh. And he had told her so. She had said the same
back to him.
Suddenly she was there, in front of him. Par had to look up slightly
to reach her eyes, since she was a little more than an inch taller.
She was quite pretty, with straight, brown shoulder-length hair and
brown eyes. He was just thinking how much more attractive she was than
he had expected, when it happened.
Theorem smiled.
Par almost lost his balance. It was a devastating smile, big and
toothy, warm and genuine. Her whole face lit up with a fire of
animation. That smile sealed it.
She had kept her promise to herself. There was no clear image of Par
in her mind before meeting him in person. After meeting a few people
from Altos at a party in Munich the year before, she had tried not to
create images of people based on their on-line personalities. That way
she would never suffer disappointment.
Par and Theorem picked up her bags and got into Brian's car. Brian, a
friend who offered to play airport taxi because Par didn't have a car,
thought Theorem was pretty cool. A six-foot-tall French-speaking Swiss
woman. It was definitely cool. They drove back to Par's house. Then
Brian came in for a chat.
Brian asked Theorem all sorts of questions. He was really curious,
because he had never met anyone from Europe before. Par kept trying to
encourage his friend to leave but Brian wanted to know all about life
in Switzerland. What was the weather like? Did people ski all the
time?
Par kept looking Brian in the eye and then staring hard at the door.
Did most Swiss speak English? What other languages did she know? A lot
of people skied in California. It was so cool talking to someone from
halfway around the world.
Par did the silent chin-nudge toward the door and, at last, Brian got
the hint. Par ushered his friend out of the house. Brian was only
there for about ten minutes, but it felt like a year. When Par and
Theorem were alone, they talked a bit, then Par suggested they go for
a walk.
Halfway down the block, Par tentatively reached for her hand and took
it in his own. She seemed to like it. Her hand was warm. They talked a
bit more, then Par stopped. He turned to face her. He paused, and then
told her something he had told her before over the telephone,
something they both knew already.
Theorem kissed him. It startled Par. He was completely unprepared.
Then Theorem said the same words back to him.
When they returned to the house, things progressed from there. They
spent two and a half weeks in each other's arms—and they were
glorious, sun-drenched weeks. The relationship proved to be far, far
better in person than it had ever been on-line or on the telephone.
Theorem had captivated Par, and Par, in turn, created a state of bliss
in Theorem.
Par showed her around his little world in northern California. They
visited a few tourist sites, but mostly they just spent a lot of time
at home. They talked, day and night, about everything.
Then it was time for Theorem to leave, to return to her job and her
life in Switzerland. Her departure was hard—driving to the airport,
seeing her board the plane—it was heart-wrenching. Theorem looked
very upset. Par just managed to hold it together until the plane took
off.
For two and a half weeks, Theorem had blotted out Par's approaching
court case. As she flew away, the dark reality of the case descended
on him.
The fish liked to watch.
Par sat at the borrowed computer all night in the dark, with only the
dull glow of his monitor lighting the room, and the fish would all
swim over to the side of their tank and peer out at him. When things
were quiet on-line, Par's attention wandered to the eel and the lion
fish. Maybe they were attracted to the phosphorescence of the computer
screen. Whatever the reason, they certainly liked to hover there. It
was eerie.
Par took a few more drags of his joint, watched the fish some more,
drank his Coke and then turned his attention back to his computer.
That night, Par saw something he shouldn't have. Not the usual hacker
stuff. Not the inside of a university. Not even the inside of an
international bank containing private financial information about
Middle Eastern sheiks.
What he saw was information about some sort of killer spy
satellite—those are the words Par used to describe it to other
hackers. He said the satellite was capable of shooting down other
satellites caught spying, and he saw it inside a machine connected to
TRW's Space and Defense division network. He stumbled upon it much the
same way Force had accidentally found the CitiSaudi machine—through
scanning. Par didn't say much else about it because the discovery
scared the hell out of him.
Suddenly, he felt like the man who knew too much. He'd been in and out
of so many military systems, seen so much sensitive material, that he
had become a little blasé about the whole thing. The information was
cool to read but, God knows, he never intended to actually do anything
with it. It was just a prize, a glittering trophy testifying to his
prowess as a hacker. But this discovery shook him up, slapped him in
the face, made him realise he was exposed.
What would the Secret Service do to him when they found out? Hand him
another little traffic ticket titled `502C'? No way. Let him tell the
jury at his trial everything he knew? Let the newspapers print it? Not
a snowball's chance in hell.
This was the era of Ronald Reagan and George Bush, of space defence
initiatives, of huge defence budgets and very paranoid military
commanders who viewed the world as one giant battlefield with the evil
empire of the Soviet Union.
Would the US government just lock him up and throw away the key? Would
it want to risk him talking to other prisoners—hardened criminals who
knew how to make a dollar from that sort of information? Definitely
not.
That left just one option. Elimination.
It was not a pretty thought. But to the seventeen-year-old hacker it
was a very plausible one. Par considered what he could do and came up
with what seemed to be the only solution.
Run.