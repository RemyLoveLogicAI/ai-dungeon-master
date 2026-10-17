# D&D AI Dungeon Master: player journey and edition profiles

Source date: October 16, 2026, America/Los_Angeles.

Status: proposed product and acceptance specification. This document develops
the user's requested experience; it does not claim those capabilities have
been implemented. Edition facts are linked to primary sources. DM behavior,
screen designs, orchestration, and release gates below are product proposals.

## 1. Product commitment

Build a deeply D&D-native prototype. The player meets an explicitly identified
AI Dungeon Master, creates a character with its help, establishes a campaign,
and plays through an evolving world. Agents generate narration, dialogue,
illustrations, music, and the interface in response to decisions. Rules,
consequences, continuity, and the player's authorship hold the experience
together. Generalizing this into a platform for other games comes after this
D&D experience works.

The DM's personality should convey an enthusiastic D&D expert: curious about
the player's character, precise about mechanics, generous with explanations,
and invested in the campaign. Expertise appears through useful guidance and
consistent rulings. It should never require overwhelming the player with lore
or speaking as though it were a human.

Core requirements:

- Start with meeting the DM and character creation, before the adventure.
- Support complete newcomers, returning players, edition switchers, and experts.
- Make guidance adjustable at any time, separately for different topics.
- Build around the chosen edition and its actual procedures and vocabulary.
- Offer suggested actions and accept freeform actions throughout play.
- Keep the player in control of character decisions and meaningful choices.
- Generate the interface as well as its content, using validated components.
- Preserve campaign facts, mechanical resources, relationships, and consequences.
- Distinguish published rules, selected optional rules, and table rulings.
- Make availability honest: a designed edition profile is not implemented support.

“From never playing to a level 140 mage” describes the breadth of assistance
the user wants. Character levels and advancement must follow the selected
rules; any exceptional progression requires a separately named rules extension.

## 2. Starting point in this repository

| Area | Observed foundation | Required experience |
| --- | --- | --- |
| Opening | Browser loads an authored scene | Meet the DM, establish preferences, create a character |
| Narrative | Fixed scenario and choice graph | Generated situations with meaningful freeform decisions |
| Rules | Original, system-neutral D20 combat | Validated, edition-specific D&D rules and procedures |
| DM | No live model or agent runtime | One coherent AI DM backed by specialist agents |
| Interface | Python-built declarative blueprints | Agent-composed, validated contextual surfaces |
| Imagery | No live image pipeline | Consistent character and scene illustrations |
| Audio | Procedural sound effects | Generated music, ambience, and optional voice |
| Continuity | Reference session and encounter-log foundations | Durable campaign and character state |

These findings come from `game_foundation.py`, `genui.py`, `web/app.js`,
`audio_synth.py`, and the existing architecture/integration documents. The
current browser's Continue action displays an intent envelope; it does not
complete a live campaign transition. A working launch is not proof of gameplay.

This specification changes the product target described in older roadmap
language. Existing repository boundaries remain useful: rules here, campaign
orchestration and persistence with MCP Games, and ephemeral rendering with
AgentSurface. Integrations need implementation and verification; this document
does not change other repositories or consolidate them.

## 3. Stage one: meet your Dungeon Master

### Player experience

The opening introduces the role before asking for account details or character
statistics. The DM explains that the player controls their character, it
portrays the world and other inhabitants, and rules and dice resolve uncertain
outcomes. The welcome should be brief enough to enter a conversation quickly.

Suggested opening copy:

> Welcome to the table. I'm your AI Dungeon Master. I'll bring the world and
> its people to life, help you create your character, and guide you through
> the rules as we play. You decide what your character attempts. How familiar
> are you with Dungeons & Dragons?

The DM may have an optional name, voice, and presentation style. It must keep
its AI identity explicit. Supporting agents remain coordinated behind this
single player-facing DM; the player should not have to manage an agent team.

### Generated interface and media

A calm welcome surface contains the DM introduction, experience choices,
accessibility controls, and a way to resume a campaign. Optional music starts
after player interaction and can be muted immediately. Decorative generation
does not block beginning setup.

### Exit condition

The player understands who runs the game and who controls their character.
They can begin, resume, or ask a question. No adventure state has been created
on their behalf without their choices.

## 4. Stage two: learn the player, not just their level

### Calibration

Ask one useful question at a time. Start with selectable answers and allow
ordinary language:

- “I've never played.” Explain the basic play loop and vocabulary through examples.
- “I know a little.” Offer reminders without repeating an entire introduction.
- “I'm returning.” Ask which edition they remember and explain relevant changes.
- “I play regularly.” Offer compact setup and detailed build controls.
- “I know another edition.” Teach differences rather than treating them as a beginner.

Then establish the edition they know, preferred explanation depth, preferred
input mode, and any accessibility needs they choose to share. No quiz is
required. Let someone ask for advanced rules detail while receiving help with
roleplaying, or the reverse.

Player experience, character level, and challenge preference are separate
settings. Familiarity with fifth edition does not imply familiarity with AD&D.
Learning support must not secretly change dice, enemy statistics, or difficulty.

### Guidance controls

Offer “Guide me,” “Remind me when useful,” and “Let me lead.” Keep persistent
actions for “Explain that,” “Show the rule,” and “What could I try?” A player
can switch modes without restarting or losing a character.

### Exit condition

The session has an editable learning profile. A newcomer can describe the
basic loop in their own words or simply choose to learn during play; neither
is a test gate.

## 5. Stage three: establish the edition and rules sources

### Edition selection

Present major edition families with plain-language descriptions and optional
historical detail. Experienced players can select the exact version directly.
Newcomers can ask the DM to explain tradeoffs. Returning players can identify a
book, year, or familiar terms and receive a proposed match to confirm.

Each campaign records its edition, rulebook revision, enabled sourcebooks,
optional rules, and house rules. These settings govern character creation,
spells, monsters, actions, saving throws, advancement, and teaching examples.
Setting lore is recorded separately; choosing a world does not change rules.

The profiles in section 14 cover the main published families. Specific
printings, starter sets, supplements, and variant systems require explicit
source selection rather than an assumption that a broad edition name includes
everything ever published for it.

### Honest availability

Each profile has separate statuses for designed, sourced, implemented, and
verified. Only a profile that passes its required play and creation checks can
be selected for a fully supported campaign. Unavailable editions can be
previewed in a clearly labeled planning view. No edition selector may simply
route every choice through the present generic D20 engine.

### Exit condition

A readable campaign rules summary identifies the exact profile and enabled
options. Unresolved source questions are visible before they affect play.
Changing edition after character creation requires a reviewed conversion;
changing a label cannot silently convert a character.

## 6. Stage four: session zero and campaign establishment

### Agree on the table

Establish the campaign's tone, themes, desired balance of exploration, social
interaction and combat, session length, and appetite for complexity. Ask about
content the player wants included or avoided without demanding personal reasons.
Offer pause, skip, and fade-out controls during play.

Agree on practical rules: advancement method where the edition supports
choices, optional modules, visibility of rolls, how uncertain rulings are
handled, and how lethal a campaign the player wants. Show the practical
consequences of those settings in ordinary language. Distinguish instruction
depth from challenge.

### Party and campaign structure

Ask whether the player is adventuring alone, playing alongside companions, or
joining a human group. A solo campaign needs encounters and objectives built
for that arrangement; do not assume a four-character party. AI companions have
their own goals and personalities but must not solve every problem or take
control of the player's character.

Human-group play is a later availability branch, with additional requirements:
each player controls their assigned characters, receives their own learning
settings and private knowledge, and participates in shared table agreements.
The DM needs a clear turn/input queue and must resolve conflicting declarations
before committing an outcome. One player's approval cannot replace another
player's required character decision. Group play cannot be advertised as
supported until these ownership and coordination checks pass.

Offer generated campaign pitches based on the agreed edition and preferences.
Describe what the characters will do, what gives them a reason to work
together, and what kinds of choices matter. Keep consequential options such
as starting level, initial wealth, and established world status visible.

### Generated surface

A campaign workspace presents the pitch, table agreements, party plan, and
editable preferences. Generate a setting mood board and musical direction
after the player chooses a direction. The player can postpone these assets.

### Exit condition

The player approves the campaign premise and table agreements. The DM has
enough context to guide a character who belongs in this campaign.

## 7. Stage five: discover the character concept

### Start with imagination

Ask what the player wants to do or experience. “I want to study forbidden
magic,” “I want to protect people,” and “I don't know yet” are valid starts.
Offer a small set of contrasting concepts, explain their play experience, and
invite the player to combine or reject them.

Translate the concept into legal options from the selected edition. Explain
what those choices enable now, their complexity, and their later development.
Distinguish a flavor suggestion from a mechanical promise: calling someone a
dragon scholar does not automatically grant unavailable powers.

### Beginner and expert paths

A beginner can build through conversation with reversible recommendations.
An expert can start with a specific class, ability distribution, sourcebook,
or build goal. Either can inspect the full sheet, change course, or ask for
more detail. Recommendations explain tradeoffs; they do not select the
player's personality, morality, or long-term decisions for them.

### Exit condition

The player owns a short concept statement, a reason to adventure, and a
proposed mechanical direction. Any mismatch with the campaign or edition has
been explained and resolved.

## 8. Stage six: build a legal character, together

### Conversational order and dependency order

The DM may discuss ideas in the order that feels natural. The actual creation
process must follow the selected edition's dependencies and restrictions.
Modern class/species/background menus cannot stand in for every edition.

Every meaningful choice includes what it changes, why it might fit, the
available alternatives, and a way to undo it. Beginners see a few useful
options first; experts can browse and compare all enabled options.

### Mechanical walkthrough

Work through these topics where the edition requires them:

| Topic | DM's responsibility | Interface behavior |
| --- | --- | --- |
| Abilities | Explain the abilities and the allowed generation method | Show recorded rolls or allocation costs and valid edits |
| Identity options | Explain edition-specific race/species and class relationships | Reveal valid combinations and explain restrictions |
| Class and advancement | Explain what the class does in actual play | Show starting features and relevant future choices |
| Background and proficiencies | Apply only the selected profile's systems | Trace each granted proficiency or benefit to its source |
| Skills and specializations | Explain uses, dependencies, and tradeoffs | Enforce ranks, selections, or other limits where applicable |
| Feats, powers, spells | Explain prerequisites, timing, costs, targeting, and recovery | Offer comparisons and reject invalid choices with repair guidance |
| Equipment | Explain affordability, carrying rules, and practical utility | Show purchases, remaining funds, and changed derived statistics |
| Derived values | Calculate defenses, hit points, saves, movement, attacks, and resources | Offer a readable calculation and rule reference |
| Higher-level starts | Apply every required advancement step | Detect missing intermediate choices and validate the resulting sheet |

Dice used in creation must be recorded. Regenerating a portrait or explanation
cannot reroll ability scores. Editing a prerequisite invalidates dependent
choices visibly and offers a repair path; it never silently removes a spell
or feat. Backtracking does not spend an additional purchase or duplicate an
item. Random character generation is optional and reviewable.

### Spellcaster teaching

For a magical character, explain the edition's distinct concepts of learning,
knowing, preparing, casting, expending, and recovering spells. Teach component,
targeting, concentration, interruption, and resource rules only where they
apply in the active profile. Make the distinction between spell level and
character level clear where relevant. A practice action demonstrates the
chosen character's actual capabilities.

### Exit condition

An independent rules validation accepts the sheet and reports no unresolved
required decisions. The player can understand their main options without
memorizing the entire sheet. Generation quality cannot substitute for legality.

## 9. Stage seven: establish identity, relationships, and presentation

### Make the character part of the world

Help establish a name, appearance, voice, temperament, personal goal, important
relationship, and reason to join the campaign. These are prompts, not a
mandatory autobiography. The player can begin with a sketch and discover
details later.

Offer backstory hooks tied to places and NPCs. Confirm invented personal facts
before making them part of the character's history. Separate what the player
has agreed is true from the DM's hidden plans and possible future revelations.
The DM does not dictate the character's thoughts or force an emotional reaction.

### Generate assets from an approved identity

Create a portrait and optional voice from the agreed description. Store a
consistent appearance reference for future illustrations. Separate narrative
appearance from mechanical equipment: a portrait cannot grant armor or a
weapon the sheet does not contain. Regenerating artwork preserves the sheet.

The player can accept an image, request changes, or continue with a placeholder.
Illustrations and music must not reveal hidden ancestry, a disguised NPC,
unseen enemies, or future plot twists.

Offer an optional character musical theme, generated from the agreed identity
and campaign tone. Reuse or vary that theme at meaningful moments. Musical
style is a player preference; a class or ancestry choice must not force one
stereotyped sound or prevent the player from changing it.

### Exit condition

The player approves their character summary and the facts that connect it to
the campaign. Media work may still be pending without blocking play.

## 10. Stage eight: learn the sheet and prepare to play

Give a short tour of this particular character: how to attempt something,
what their common combat choices are, what resources need tracking, and how
to ask for help. Explain terminology with examples drawn from the character.

Offer an optional practice situation covering conversation, exploration, and
one relevant mechanical action. Clearly mark whether practice is outside the
campaign or a real opening scene; practice outside the campaign does not
consume permanent resources or award progression.

Show the edition, party, campaign premise, agreed rules, and final sheet for
review. Experienced players can skip instruction and go directly to this check.
Newcomers can ask the DM to continue explaining during play.

Exit condition: the player approves the starting character and campaign and
chooses to begin. Setup can be saved and resumed at any earlier stage.

## 11. Stage nine: the first adventure and the ongoing play loop

### Begin with a situation worth acting on

Generate an opening that connects to the character's motives and the agreed
campaign. Establish what they can perceive, an immediate situation, and room
to choose. Avoid delivering a long setting lecture before the first action.
Suggested actions are invitations; freeform input remains available.

The DM repeatedly performs this loop:

1. Describe the situation from the character's available information.
2. Receive the player's intended action in ordinary language or through controls.
3. Clarify only ambiguities that change the outcome or commitment.
4. Determine whether the action succeeds directly, needs a rules procedure,
   or requires a declared table ruling.
5. Resolve mechanics using the correct edition, character state, and recorded
   dice, pausing for any eligible player response before its deadline passes.
6. Commit consequences and resource changes once.
7. Narrate the result and coordinate the next interface, image, and audio.

A player should not need to name the correct skill to describe a sensible
action. The DM should also avoid unnecessary rolls for actions the selected
rules resolve without one. A failed roll must be honored; its narrative
consequence should suit the actual situation rather than being an unrelated
punishment.

### Guidance across play

| Situation | Beginner support | Experienced-player support |
| --- | --- | --- |
| Exploration | Explain practical options, time, light, supplies, and risk as relevant | Compact resource tracking and precise procedure details on demand |
| Social scenes | Explain that ordinary speech or described intent is enough | Persistent NPC motives, nuanced responses, and room for complex plans |
| Combat | Explain the character's legal options and resource costs | Exact timing, targeting, movement, defenses, and interrupt windows |
| Spellcasting | Preview what the selected spell can do and what it costs | Precise version, interactions, and source-grounded adjudication |
| Investigation | Distinguish discovered evidence from guesses | A consistent mystery and consequences for investigative choices |
| Failure | Explain the result and available next steps | Preserve challenge, tactical consequences, and fair adjudication |
| Defeat or death | Explain the applicable rules and agreed campaign options clearly | Apply the same agreed rules without hidden rescues |

Hints must use player-visible knowledge. If the DM is uncertain about a rule,
it retrieves the selected source. If the source remains unresolved, it says so
and proposes a recorded temporary ruling under the table agreement. It must
not invent a citation or claim an unsupported procedure is an official rule.

### Responses and interruptions

Where the edition permits a reaction, interrupt, or other timed choice, surface
it at the point required by that rule. Show the information the character is
entitled to know, available responses, their costs, and a clear decline option.
Do not finalize damage or another consequence before a relevant response
window has closed. Some rules trigger after a roll but before its effects;
the resolver must preserve that intermediate state across pause and resume.
Resolve nested responses in the selected edition's order and commit each cost
once. Optional automation requires a player-approved policy and remains editable.

### Contextual generated UI

During exploration, the DM can compose a location view, inventory shortcuts,
known clues, and travel options. A conversation can emphasize dialogue,
relationships, and visible evidence. Combat can introduce a tactical view,
initiative, current effects, relevant resources, and legal actions.

Layout adapts, while input, help, character access, and accessibility controls
remain predictable. A newly generated layout preserves keyboard focus and
unfinished input. Actions carry stable identifiers and the state revision they
were generated for. An obsolete button refreshes with an explanation rather
than applying an action to the wrong turn.

### The craft of an expert DM

The DM's dedication should be observable during ordinary play:

- Describe useful sensory details and actionable information. An elaborate
  paragraph that leaves the player unsure what is happening is not enough.
- Give NPCs motives, limitations, and remembered experiences. They can disagree
  with the character without the DM treating the player as an opponent.
- Prepare situations with multiple plausible approaches. A creative plan
  deserves consideration even when it bypasses a planned encounter.
- Keep consequences connected to choices, elapsed time, and established facts.
  A new scene must not erase an earlier promise, injury, or escaped enemy.
- Support the character's actual capabilities. High-level magic and unusual
  strategies should matter; do not invent immunity just to preserve a plot.
- Manage tension, quiet moments, discovery, and recovery. In group play,
  distribute attention and ask before an AI companion resolves a pivotal choice.
- Offer tactical guidance when requested using what the character can know.
  Avoid announcing the best move based on hidden enemy statistics.
- Handle corrections candidly. Explain the rule or mistaken state, propose the
  smallest fair repair, and record an accepted correction without rerolling
  unrelated events.

The DM can share enthusiasm about a clever solution or interesting piece of
lore. Detailed lore discussion should be available on demand without stopping
the adventure every time a new creature or place appears.

## 12. Stage ten: downtime, advancement, and campaign mastery

### Between adventures

Support rest, recovery, shopping, research, training, crafting, travel, factions,
and other activities only as provided by the chosen rules and campaign. The
DM explains time and resource commitments before execution. Generated scenes
can make these activities personal without inventing free mechanical benefits.

### Advancement

When advancement becomes available, the DM celebrates the character's deeds
and guides every required choice. Show a before/after sheet, the reason each
change occurred, and any new resource or interaction. A short optional practice
can teach a new capability without changing campaign state.

High-level play needs more than bigger enemies. The DM must handle the scope
of the selected edition's actual capabilities and campaign procedures, while
preserving coherent consequences. Do not force every edition into identical
level tiers, advancement costs, or endgame systems.

### Continuing after death or retirement

Apply the agreed campaign's rules and consequences first. If recovery or
resurrection is available under the edition and circumstances, explain its
actual eligibility, costs, and consequences. Never promise a recovery method
the selected rules or campaign cannot provide.

The player can also create a replacement character, retire the campaign, or
take time before deciding. Guide a replacement through the same edition-aware
creation process, establish an agreed starting point, and introduce them
coherently. Preserve the former character's history, relationships, belongings,
and unresolved consequences instead of resetting the world. A replacement
character does not automatically inherit the previous character's private
knowledge or inventory.

### Growing expertise

Remember which explanations the player found helpful and which they dismissed.
Offer less instruction after repeated familiarity, with an obvious way to
bring it back. Learning history belongs to this player's guidance profile;
it is not a hidden score that determines character success.

Exit condition: advancement is legal and committed once, the player understands
new decisions, and play can resume from the updated state.

## 13. Stage eleven: closure, resumption, and long-term continuity

End a session with a concise recap, unresolved threads, current resources,
important promises, and the next situation. Let the player correct the recap;
corrections must be reconciled with recorded events rather than overwriting
unrelated facts.

On return, offer a short recap or a deeper refresher. Preserve who knows what:
an NPC secret, an unconfirmed player theory, and an established campaign fact
are different records. Relationships, inventories, conditions, world time,
travel, and ongoing effects persist as required by the active profile.

Save after meaningful committed actions and at setup checkpoints. Pausing or
resuming never rerolls a resolved event. The player can inspect their sheet
and known journal without receiving hidden DM material.

Exit condition: a resumed session matches the saved edition, sheet, resources,
world facts, and position in play, with no replayed costs or duplicated rewards.

## 14. Edition-specific player journeys

The shared stages above describe the experience contract. Each edition profile
must supply its own creation dependencies, teaching examples, sheet, resolution
procedures, source vocabulary, and progression checks. The following profiles
are design targets; none are implemented by this document.

### Original D&D, 1974 family

**Grounding and source identity.** Identify the actual printing and selected
supplements. The publisher's currently offered original-edition PDF represents
a later reproduction/revision, so “1974” alone is insufficient source identity.
The original material's relationship to Chainmail also needs an explicit
combat-procedure choice.
[Publisher listing](https://www.drivethrurpg.com/product/28306/ODD-Dungeons--Dragons-Original-Edition-0e),
[original-text preview](https://watermark.drivethrurpg.com/pdf_previews/28306-sample.pdf).

**Onboarding and creation design.** Introduce the selected early game's own
vocabulary, referee role, available characters, ability procedure, equipment,
and starting resources. Explain decisions through the character's immediate
adventuring needs. Do not insert a modern background, feat, or subclass step.

**Ongoing guidance design.** Give the player clear information about the
procedures the referee will use for exploration, encounters, combat, and
advancement. Distinguish text supplied by the selected sources from a declared
referee convention. The UI can expose supplies, time, and expedition decisions
without assuming a modern action economy.

**Verification scenario.** A character and encounter use the explicitly chosen
combat conventions and source set. Where the original text leaves a referee
decision, the DM explains and records that decision rather than presenting a
later edition's mechanic as original D&D.

### Holmes Basic

**Evidence status.** Preserve Holmes as a separate introductory profile. Direct
primary rulebook text was not retrieved in this research pass. Detailed limits,
creation formulas, combat procedures, and continuation rules remain source-audit
requirements, rather than verified implementation instructions.

**Onboarding and creation design.** Build a guided introduction using the exact
Holmes text once acquired and verified. Present only its supported character
choices, with its own vocabulary and sheet. Explain what this introductory
profile covers before the player commits to a long campaign.

**Ongoing guidance design.** Teach the selected introductory procedures through
short situations. When the character reaches the profile's supported extent,
offer an explicit, reviewed continuation into a selected rules profile. Carry
forward the character's identity and campaign history, while showing mechanical
changes that need agreement.

**Verification scenario.** The player completes the introductory scope and
reviews a continuation. The system does not silently switch to B/X, AD&D, or
fifth edition under the same Holmes label. Source acquisition and primary-text
validation are prerequisites to advertising playable support.

### Basic/Expert, B/X

**Grounding and evidence boundary.** The publisher identifies the Moldvay Basic
rulebook as the B/X Basic edition. Its detailed rules and the matching Expert
text still require direct validation for this implementation; a retrospective
product-history essay does not establish exact mechanics.
[Publisher listing](https://www.drivethrurpg.com/en/product/110274/d-d-basic-set-rulebook-b-x-ed-basic).

**Onboarding and creation design.** Develop the creation flow against the
matching Basic and Expert sources. Explain the practical consequences of the
available classes, starting equipment, and adventure procedures without
replacing them with modern fifth-edition choices. Keep the character's current
scope and the next supported stage visible.

**Ongoing guidance design.** Build a useful expedition interface around the
verified procedures for time, supplies, encounters, exploration, and combat.
Teach caution, negotiation, and retreat as available approaches, without
framing a beginner's decision to roll dice as a mistake. Extend into Expert
play using its own verified procedures and progression.

**Verification scenario.** A Basic character advances into the selected Expert
rules while retaining the correct resources, character restrictions, and
campaign consequences. BECMI or Cyclopedia procedures are not substituted
without an explicit source choice.

### BECMI

**Source structure.** Model Basic, Expert, Companion, Master, and Immortals as
explicitly selected parts of the BECMI profile. Original set texts were not all
inspected in this pass, so the exact procedures and transitions need primary
source audits. A similarly named B/X book or the Cyclopedia is not evidence
that every BECMI detail has been verified.

**Onboarding and creation design.** Begin with the supported starting stage,
then show a readable roadmap of available campaign development. Do not force
an introduction to every later system before creating the first character.
An experienced player starting later needs a reviewed history and all choices
required to reach that point.

**Ongoing guidance design.** Introduce additional campaign procedures as the
selected set makes them relevant. Generate appropriate management or adventure
surfaces from those verified procedures. If an Immortals continuation is
selected, teach its actual transition and character model rather than simply
continuing ordinary levels indefinitely.

**Verification scenario.** A campaign crossing between selected BECMI sets
receives the correct new decisions and rules explanation. The source module
changes explicitly; prior character and world consequences remain intact.

### Rules Cyclopedia

**Grounding.** The original preview provides an ordered character-creation
procedure, includes dwarf, elf, and halfling as classes, and uses descending
Armor Class. It also connects Charisma to reactions and retainers, and prime
requisites to experience. These need visible explanations rather than a
modern race/class form.
[Original-text preview](https://watermark.drivethrurpg.com/pdf_previews/17171-sample.pdf).

**Onboarding and creation design.** Follow the book's actual ability, class,
hit-point, money, equipment, derived-value, alignment, and identity steps.
Explain eligibility and the character's own advancement limits. Teach how
supplies and companions relate to the player's chosen expedition.

**Ongoing guidance design.** Build assistance for the campaign procedures the
Cyclopedia supplies, including larger-scale play where enabled and verified.
Its publisher description advertises a broad level range; that must not be
turned into a claim that every class has the same progression or limits.
[Publisher description](https://www.drivethrurpg.com/en/product/17171/d-d-rules-cyclopedia-basic).

**Verification scenario.** Character creation and advancement use the
Cyclopedia's class rules and limits, with verified descending-AC calculations.
Any extension beyond the book's supported character model is named separately
and cannot inherit “official Cyclopedia” status automatically.

### Advanced D&D, first edition

**Grounding.** The publisher lists races and classes separately. Wizards'
conversion guide confirms first-edition terminology such as magic-user and
thief, and exceptional percentile Strength. These are distinct from a modern
fifth-edition sheet.
[Player's Handbook listing](https://www.drivethrurpg.com/product/17003/Players-Handbook-1e),
[official conversion guide](https://media.wizards.com/2015/downloads/dnd/DnD_Conversions_1.0.pdf).

**Onboarding and creation design.** Explain the selected source's race/class
eligibility, ability procedures, and class-specific decisions. Make unusual
ability notation understandable where the character uses it. Present only
options the selected printings and supplements actually supply.

**Ongoing guidance design.** Source-audit and implement the exact attack,
saving-throw, initiative, spellcasting, and advancement procedures before
teaching them as official rules. Show a practical explanation alongside the
relevant rule reference. If the table chooses an optional or simplified
procedure, record it explicitly.

**Verification scenario.** A first-edition character passes creation and a
spellcasting encounter using its own verified procedures. A second-edition
kit, later proficiency rule, or modern reaction cannot appear by default.

### Advanced D&D, second edition

**Grounding.** Wizards' conversion guidance recognizes secondary skills,
nonweapon proficiencies, and kits as possible second-edition character details.
The guide's conditional treatment means these cannot all be mandatory steps
for every campaign.
[Official conversion guide](https://media.wizards.com/2015/downloads/dnd/DnD_Conversions_1.0.pdf).

**Onboarding and creation design.** Select the printing and optional sources
before presenting the creation flow. Explain which proficiency and kit choices
are active, and offer a simpler route when those options are not enabled.
Retain the edition's character terminology and verified class restrictions.
[Revised Player's Handbook listing](https://www.drivethrurpg.com/product/16868/Players-Handbook-Revised-2e).

**Ongoing guidance design.** Validate second-edition combat, saves, spellcasting,
and advancement against its own sources. Explain source-specific procedures
when they arise. Optional supplements, including alternate character systems,
need separate validation and cannot be inferred from the edition selector.

**Verification scenario.** Two campaigns with different optional-source
settings generate different required creation choices correctly. A character
without a selected kit remains legal. First-edition combat details are not
silently treated as second-edition defaults.

### Third edition, 3.0

**Evidence status.** The original 3.0 Player's Handbook was not directly inspected
in this pass. Keep it as a separate profile requiring source validation; the
verified 3.5 revision history establishes that treating them as identical would
lose meaningful changes.
[3.5 publisher revision description](https://www.drivethrurpg.com/en/product/148008/player-s-handbook-3-5).

**Onboarding and creation design.** Develop the 3.0 creation order, class and
race options, skill allocation, feats, and spells against the original sources.
Explain build dependencies with a readable progression preview. An expert can
inspect prerequisites while a beginner receives a small set of legal suggestions.

**Ongoing guidance design.** Teach and validate the selected 3.0 action,
positioning, attack, defense, and magic procedures. Preserve spell and skill
versions even when a 3.5 source uses a similar name. Optional additions require
an enabled source and a verified interaction.

**Verification scenario.** A 3.0 character retains its legal features through
advancement. Moving to 3.5 creates a reviewable conversion with identified
changes, rather than silently updating the campaign's rules label.

### Third edition, revised 3.5

**Grounding.** The publisher identifies changes to classes, spells, skills,
and feats in the revision. The original preview establishes skill-point
allocation, class/cross-class distinctions, feat prerequisites, and grid-based
combat assumptions. Those justify a dependency-aware builder and contextual
positioning guidance.
[Publisher description](https://www.drivethrurpg.com/en/product/148008/player-s-handbook-3-5),
[original-text preview](https://watermark.drivethrurpg.com/pdf_previews/148008-sample.pdf).

**Onboarding and creation design.** Show the practical costs of skill allocation,
the prerequisites of feats, and the character's spell choices. Let the player
preview a build without committing future advancement. Explain why a proposed
choice is unavailable and what legal alternatives preserve the concept.

**Ongoing guidance design.** Validate action costs, positioning, threatened
areas, and spell interactions using the enabled sources. Explain complex
sequences one decision at a time. Track the actual sources for later additions
instead of assuming all action types or options were in the original core book.

**Verification scenario.** Editing a skill or ability prerequisite flags its
real dependencies; a tactical action uses the selected rules once and exposes
its actual cost. A similarly named 3.0 feature does not overwrite its version.

### Fourth edition

**Source boundary.** Select core books, updates, and optional sources explicitly.
The verified fourth-edition Essentials preview supplies creation, powers,
progression, and skill-challenge material, but it cannot establish every core
class's power schedule. Full core procedures still require direct source audit.
[Original Essentials preview](https://watermark.drivethrurpg.com/pdf_previews/156573-sample.pdf).

**Onboarding and creation design.** Explain the chosen class's contribution to
the party and how its available powers work in concrete situations. Generate
readable power cards with actual usage, targeting, timing, and recovery
requirements. Apply the chosen build's progression rather than assigning
identical starting powers to every class.

**Ongoing guidance design.** Develop precise positional and team-play assistance,
with conditions, effects, defenses, and timed responses drawn from the selected
sources. Support exploration and social situations with the same attention to
character agency; the experience must not consist only of combat encounters.

**Verification scenario.** A response or effect-duration choice appears at its
correct trigger and survives interruption. Different class builds receive their
actual resources and advancement choices, with no assumed universal schedule.

### Fourth edition, Essentials source/build profile

**Grounding.** The publisher explicitly describes Essentials material as usable
with existing fourth-edition characters. The preview identifies builds such as
knight, slayer, thief, mage, and warpriest. Essentials therefore belongs within
fourth edition with an explicit source/build selection.
[Heroes of the Fallen Lands listing](https://www.drivethrurpg.com/en/product/156573/player-essentials-heroes-of-the-fallen-lands-4e),
[original-text preview](https://watermark.drivethrurpg.com/pdf_previews/156573-sample.pdf).

**Onboarding and creation design.** Explain the selected build's play pattern,
then present its actual creation choices. A streamlined introduction must still
show consequential selections and their costs. Do not reuse a core-class form
unless its requirements genuinely match the selected build.

**Ongoing guidance design.** Generate controls and teaching from the build's own
features and progression. When a party mixes source sets, keep each character's
rules and recovery procedures precise while using the shared fourth-edition
resolution procedures.

**Verification scenario.** An Essentials character and a core-source character
can participate in the same tested encounter, each retaining its validated
build and resources. An Essentials selection does not receive an unrelated
class's assumed power schedule.

### Fifth edition, 2014 rules

**Grounding.** The published creation walkthrough covers race, class, abilities,
description, equipment, and bringing the party together. Its advancement table
extends through level 20. Optional systems and later supplements need their own
selection; an edition name is not a sourcebook policy.
[2014 character creation](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/step-by-step-characters).

**Onboarding design.** Teach checks, attacks, saves, and the character's
proficiencies using their actual sheet. The first combat walkthrough should
explain movement, actions, bonus actions when available, reactions, and the
character's own recovery rules. Introduce concentration when the character
has a relevant spell. Keep optional-feat and multiclass teaching behind the
campaign's enabled options.

**Character creation design.** Present race, class, background, proficiencies,
equipment, and starting spell decisions in a coherent flow. Show subclass
choices at the level required by the chosen class. Source-specific ability
adjustments must be explicit. Support a detailed build preview and a
conversation-led route to the same validated sheet.

**Ongoing guidance design.** Explain the cost and legal use of the current
character's abilities. Show concentration and duration where relevant, track
resources and rests, and explain changes during advancement. When a player
knows revised rules, identify the specific legacy rule involved rather than
giving generic advice about fifth edition.

**Verification scenario.** A 2014 character and a revised-rules character with
similarly named features each retain their own rules, sources, and costs.
The DM cannot answer a 2014 question by silently using a revised spell.

### Fifth edition, revised 2024 rules

**Grounding.** The revised walkthrough starts with class, then origin,
abilities, alignment, and remaining details. Origin includes background and
species. Backgrounds specify ability adjustments and an Origin feat. Its
published compatibility instructions explain how older backgrounds and species
are used. These instructions must be implemented explicitly when those sources
are enabled.
[2024 character creation](https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character),
[character origins](https://www.dndbeyond.com/sources/dnd/br-2024/character-origins).

**Onboarding design.** Ask what the character wants to do, then explain the
revised class and origin choices. Give players familiar with 2014 rules a
specific changes tour. Revised mechanics such as Weapon Mastery need teaching
when the selected class provides them; keep teaching based on actual character
features rather than presenting every new term immediately.
[2024 character classes](https://www.dndbeyond.com/sources/dnd/br-2024/character-classes).

**Character creation design.** Connect the concept to class, background,
species, and legal ability allocation. Explain the practical effect of the
background's feat and proficiencies. Keep older-content compatibility choices
visible on the sheet. Label every class, spell, and feature with its version
where a similarly named older option exists.

**Ongoing guidance design.** Generate controls from the revised action and
feature definitions. Explain why a capability behaves differently from an
older version when asked. Offer deeper rules explanations without making them
mandatory. Use the actual advancement schedule and character resources.

**Verification scenario.** A legacy-origin choice is processed using the
selected compatibility rule and does not double-count ability adjustments or
omit a required feat. Revised class and spell behavior survives save/resume.

**Source identity.** Keep the user-facing 2024-rules label and exact source
revision separate. The official SRD page currently identifies SRD 5.2.1, with
prior versions retained; this is a source revision, not a reason to relabel or
silently update an existing campaign.
[Official SRD versions](https://www.dndbeyond.com/srd).

## 15. Coordinated AI generation

### One DM, bounded specialist responsibilities

| Role | Responsibility | Required constraint |
| --- | --- | --- |
| Dungeon Master | Maintain the conversation, interpret intent, plan scenes, adjudicate discretionary situations | Preserve player agency and distinguish official rules from rulings |
| Rules specialist | Retrieve the selected source and request mechanical validation/resolution | Never substitute a different edition when evidence is missing |
| Character guide | Explain choices and propose character changes | Player reviews meaningful choices; validator checks legality |
| Campaign keeper | Record committed events, relationships, resources, and known facts | Keep player knowledge separate from DM secrets |
| Visual artist | Generate portraits, environments, items, and scene art | Use approved identity references and current visible facts |
| Composer and sound designer | Generate music, ambience, and optional voices | Respect mute controls and avoid audible spoilers |
| Interface composer | Generate contextual layouts and bindings | Use validated components and allowed, state-checked actions |

These are responsibility boundaries, not a requirement to run seven model calls
for every action. The DM can reuse a valid scene illustration, continue the
current musical theme, or update one UI component when that fits the moment.
Player decisions determine what needs generation. This prevents every small
action from creating an unnecessary wait while retaining genuine generation.

### Turn and media coordination

Resolve and commit the authoritative outcome before representing that outcome
as fact. Narrative can then appear promptly while larger assets finish. Attach
each generation request to its campaign, scene, state revision, and approved
references. Discard stale results from a scene the player has already left.

Media completion must not advance turns, alter dice, consume resources, or
change character facts. An image failure leaves readable text and a retry
option. A music failure leaves play usable. A DM model outage must be stated
clearly; an authored fallback cannot be presented as live AI play.

Generated UI is a declarative surface. The host validates component structure,
allowed intents, campaign identity, state revision, and rules legality before
an action takes effect. Arbitrary model-authored executable code is outside
the rendering contract.

## 16. Acceptance scenarios

These are release requirements for future implementation, not tests run or
passed by this specification.

| Scenario | Observable pass condition |
| --- | --- |
| Complete newcomer | Meets an explicitly identified AI DM, finishes a legal character, and takes a meaningful action without reading a rulebook |
| Returning player | Selects their familiar edition and receives targeted explanations rather than a generic fifth-edition tutorial |
| Expert builder | Uses detailed controls, sees legal dependencies and sources, and skips basic teaching |
| Beginner at higher level | Receives deeper guidance without being silently forced to level one |
| Edit during creation | A prerequisite change flags dependent choices and repairs them without hidden replacement or duplicated costs |
| Magical character | The guide explains the selected edition's actual casting and recovery model using the created sheet |
| Edition distinction | The same proposed action is resolved by each tested profile's own rules, including procedures that are not D20 checks |
| Unavailable rule | The DM names the gap and offers a reviewable table ruling or alternative; no invented source citation appears |
| Freeform action | A sensible unexpected action can be adjudicated without requiring an existing button |
| Solo campaign | Party structure and encounters fit the agreed arrangement, and companions preserve player decision-making |
| Roll integrity | Explanations, UI regeneration, and media retries leave recorded dice and outcomes unchanged |
| Retry or double submission | A committed action spends resources and awards rewards once |
| Timed response | An eligible interrupt pauses at the correct rules window, survives interruption, and spends its resource once after the player responds |
| Delayed image or music | Playback and scene art never revert to an obsolete scene or reveal hidden information |
| UI regeneration | Input, focus, character access, and help remain usable; stale actions cannot mutate a later state |
| Session interruption | Character creation or campaign play resumes from the last committed checkpoint |
| Advancement | Required choices and calculations pass independent validation with a readable before/after sheet |
| Death or retirement | Available continuation paths follow the agreed rules, and a replacement character enters a world that retains the prior character's consequences |
| Human-group availability | Shared campaigns are enabled only with character ownership, private knowledge, input coordination, and individual guidance verified |
| Genuine generation | A provider-backed run records actual text, image, music, and UI generation attributable to player decisions; fixture mode is labeled |
| High-level scope | Each advertised profile passes advanced scenarios for the level range and sourcebooks it claims |

## 17. Implementation sequence and completion gates

This is a proposed sequence, not a decision to drop any requested edition.
Keep every edition's experience specified while implementing and verifying
them in bounded increments.

1. Establish the welcome, learning profile, session-zero agreements, edition
   identity, and resumable character draft. Verify the beginner and expert paths.
2. Implement a sourced modern-edition profile end to end, including its legal
   creation and gameplay procedures. A 2024-rules campaign is a practical first
   candidate because its creation and play sources are directly available; the
   implemented source set must be explicit.
3. Prove one real generated decision end to end: commit a legal outcome, then
   produce coherent narration, illustration, music, and an agent-composed UI.
4. Add the other fifth-edition profile as a separate validated implementation.
   Prove that similarly named spells and features retain their own versions.
5. Add classic, AD&D, third-edition, and fourth-edition profiles against their
   individual sources and acceptance scenarios. Introduce Basic-family
   continuations and optional modules explicitly rather than flattening them.
6. Expand high-level play, campaign duration, and enabled sourcebooks with
   demonstrated coverage. Only then extract a universal game-platform design.

Completion of the requested product requires more than this sequence's first
playable slice. Each advertised edition needs its own coverage evidence. The
present demo has no supported-edition status to promote automatically.

## 18. Evidence and remaining decisions

The user's same-thread directions are the canonical product requirements:
fully generative play, D&D first, universalization later, character creation
first, deep guidance from beginner to expert, and treatment by edition.

Modern rules references:

- [2014 Basic Rules: character creation](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/step-by-step-characters)
- [2024 Basic Rules: character creation](https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character)
- [2024 Basic Rules: character origins](https://www.dndbeyond.com/sources/dnd/br-2024/character-origins)
- [2024 Basic Rules: playing the game](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game)
- [Official SRD versions and downloads](https://www.dndbeyond.com/srd)

The SRD is a defined content subset; its availability is not evidence that
every published D&D option or setting is implemented or included. Exact source
sets, source revisions, and availability must remain visible.

Implementation still needs provider selection, generation budgets and timing
targets, campaign storage integration, rules-source coverage, and an initial
edition implementation order. These do not block this experience specification.
No paid generation, remote deployment, publishing, or external project changes
were performed to produce it.

Initial context retrieval used direct Mem and Supermemory connectors because
MCP Router tools were unavailable in the parent lane. Historical-source research
subsequently used routed Firecrawl tools when they became available in the
research lane. The retrieved Mem results did not establish a matching edition
requirement; Supermemory returned no match. The current user directions take
precedence. No remote memory records were written.

The user subsequently supplied a pasted parallel handoff describing edits to
this same document. Its useful experience ideas were reconciled here. Combined
historical-edition sections and exact, unsourced mechanical claims were replaced
with distinct profiles, primary references where retrieved, and explicit source
audit requirements where evidence is missing. The handoff's claim of a completed
Git commit was not adopted as evidence of repository state.
