"""Hand-written cases: how people actually ask, in English, Hindi and Hinglish.

Each case names the IPC provisions its facts describe. The BNS answer is derived from the
correspondence graph rather than typed in, so no remembered (and possibly wrong) BNS
number enters the ground truth. Only offences with no IPC origin name BNS sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lexbridge.bundle import Bundle
from lexbridge.eval.cases import Case, Category, case_id
from lexbridge.schema import Act, act_in_force_on


@dataclass(frozen=True)
class Hand:
    question: str
    category: Category
    # A day inside the stated period; None when undated or the period straddles the cutover.
    day: date | None = None
    ipc: tuple[str, ...] = ()
    # Only where the graph has no answer (a provision new in the BNS, or an unmapped IPC
    # section). Given, it replaces the derived BNS targets; ipc then lists the old-code
    # provisions that are the wrong law for a post-cutover date.
    bns: tuple[str, ...] = ()
    # When the question itself names the code, no date is needed.
    act: Act | None = None


LAY, HINDI, EDGE, TRICKY, OUT = (
    Category.LAY, Category.HINDI, Category.BOUNDARY, Category.TRICKY, Category.OUT_OF_SCOPE)
CHEATING, THEFT = ("415", "417", "420"), ("378", "379")
HURT, MURDER = ("319", "321", "323"), ("300", "302")

HAND: tuple[Hand, ...] = (
    Hand("Someone took my phone out of my bag on a crowded bus on 3 May 2024. What offence "
         "is that?", LAY, date(2024, 5, 3), THEFT),
    Hand("A shopkeeper sold me a fake gold chain claiming it was real, in September 2024. "
         "What can he be charged with?", LAY, date(2024, 9, 1), CHEATING),
    Hand("My husband and in-laws keep harassing me for more dowry. Which law protects me?",
         LAY, None, ("498A",)),
    Hand("My neighbour threatened to kill me if I complain to the police. This was in "
         "January 2025.", LAY, date(2025, 1, 1), ("503", "506")),
    Hand("A man has been following me home and messaging me again and again although I told "
         "him to stop, since August 2024.", LAY, date(2024, 8, 1), ("354D",)),
    Hand("My employer kept the money I gave him to deposit in the bank and spent it, back "
         "in 2023.", LAY, date(2023, 1, 1), ("405", "406")),
    Hand("Someone hit me and fractured my arm on 12 February 2025.", LAY, date(2025, 2, 12),
         ("320", "325")),
    Hand("A group of five armed men robbed a house in our village in March 2024.", LAY,
         date(2024, 3, 1), ("391", "395")),
    Hand("A person forged my signature on a property document in October 2024.", LAY,
         date(2024, 10, 1), ("463", "465")),
    Hand("A speeding driver ran over a pedestrian, who died, in November 2024. What is the "
         "offence?", LAY, date(2024, 11, 1), ("304A",)),
    Hand("Someone posted false claims online that I am a thief and ruined my reputation. "
         "It was in April 2024.", LAY, date(2024, 4, 1), ("499", "500")),
    Hand("A man threatened to publish my private photos unless I paid him, in December "
         "2024.", LAY, date(2024, 12, 1), ("383", "384")),
    Hand("A woman was secretly filmed while changing clothes in February 2024.", LAY,
         date(2024, 2, 1), ("354C",)),
    Hand("My neighbour deliberately set my motorbike on fire. What is the punishment?", LAY,
         None, ("425", "435")),
    Hand("Someone entered my house at night without permission in June 2023.", LAY,
         date(2023, 6, 1), ("441", "442", "456")),
    Hand("A man killed someone on purpose in 2022. What is the punishment?", LAY,
         date(2022, 1, 1), MURDER),
    Hand("A man stabbed someone meaning to kill him, but the victim survived, on 5 August "
         "2024.", LAY, date(2024, 8, 5), ("307",)),
    Hand("A woman died within two years of marriage after repeated dowry demands, in May "
         "2024.", LAY, date(2024, 5, 1), ("304B",)),
    Hand("Someone threw acid on a woman's face in January 2025.", LAY, date(2025, 1, 1),
         ("326A",)),
    Hand("A six-year-old took a toy from a shop. Can the child be punished?", LAY, None,
         ("82",)),
    Hand("A man killed his attacker while defending himself from a knife attack in 2023. "
         "Is he protected by law?", LAY, date(2023, 1, 1), ("96", "100")),
    Hand("Two people planned together to rob a bank but were caught before doing it, in "
         "September 2024.", LAY, date(2024, 9, 1), ("120A", "120B")),
    Hand("A student took his own life after his teacher kept harassing and humiliating him, "
         "in March 2025. Is the teacher liable?", LAY, date(2025, 3, 1), ("306",)),
    Hand("A man married a second woman while his first wife was alive, in 2021.", LAY,
         date(2021, 1, 1), ("494",)),
    Hand("Someone bought a motorcycle knowing it was stolen, in July 2024.", LAY,
         date(2024, 7, 1), ("411",)),
    Hand("A man lied under oath in court in August 2025.", LAY, date(2025, 8, 1),
         ("191", "193")),
    Hand("My business partner locked me in a room for two days in June 2024.", LAY,
         date(2024, 6, 1), ("340", "342")),
    Hand("A man made obscene gestures at a woman on the street in November 2025.", LAY,
         date(2025, 11, 1), ("509",)),
    # The cutover itself, and periods that straddle it.
    Hand("A man cheated a buyer on 30 June 2024. Which section applies?", EDGE,
         date(2024, 6, 30), CHEATING),
    Hand("A man cheated a buyer on 1 July 2024. Which section applies?", EDGE,
         date(2024, 7, 1), CHEATING),
    Hand("A theft happened in June 2024 but the FIR was only filed in August 2024. Which "
         "section applies?", EDGE, date(2024, 6, 1), THEFT),
    Hand("Someone slapped me in July 2024 and the trial starts in 2026. Which section?", EDGE,
         date(2024, 7, 1), HURT),
    Hand("A murder was committed in 2024. Which code applies?", EDGE, None, MURDER),
    Hand("Someone printed counterfeit 500 rupee notes in 2024.", EDGE, None, ("489A",)),
    # Provisions with no clean counterpart. BNS 152 is not a renumbered sedition section:
    # the table maps nothing to it, so it is asked as a BNS provision, not as a successor.
    Hand("Is it an offence to give a speech against the government in September 2024?", TRICKY,
         date(2024, 9, 1), ("124A",), bns=("152",)),
    Hand("What did section 124A of the IPC say?", TRICKY, ipc=("124A",), act=Act.IPC),
    Hand("Is attempting suicide punishable? It happened in 2020.", TRICKY, date(2020, 1, 1),
         ("309",)),
    Hand("A man on a bike pulled a gold chain from a woman's neck on 20 October 2024.", TRICKY,
         date(2024, 10, 20), ("356", "378", "379"), bns=("304",)),
    Hand("A man on a bike pulled a gold chain from a woman's neck in 2023.", TRICKY,
         date(2023, 1, 1), ("356", "378", "379")),
    Hand("A gang runs an extortion and contract-killing racket across states, since 2025.",
         TRICKY, date(2025, 1, 1), bns=("111",)),
    Hand("Does the BNS allow community service as a punishment?", TRICKY, bns=("4",),
         act=Act.BNS),
    Hand("A mob killed a man because of his caste in 2025. Which section applies?", TRICKY,
         date(2025, 1, 1), MURDER, bns=("103",)),
    # Hindi and Hinglish.
    Hand("धोखाधड़ी की सज़ा क्या है? घटना मार्च 2024 की है।", HINDI, date(2024, 3, 1), CHEATING),
    Hand("अगस्त 2024 में मेरा मोबाइल चोरी हो गया। कौन सी धारा लगेगी?", HINDI,
         date(2024, 8, 1), THEFT),
    Hand("दहेज के लिए पति और ससुराल वाले परेशान करते हैं, कौन सा कानून लागू होगा?", HINDI,
         None, ("498A",)),
    Hand("हत्या की सज़ा क्या है?", HINDI, None, MURDER),
    Hand("जनवरी 2025 में किसी ने मुझे जान से मारने की धमकी दी।", HINDI, date(2025, 1, 1),
         ("503", "506")),
    Hand("मानहानि के लिए कौन सी धारा है? मामला 2023 का है।", HINDI, date(2023, 1, 1),
         ("499", "500")),
    Hand("chori ki saza kya hai, ghatna 2022 ki hai", HINDI, date(2022, 1, 1), THEFT),
    Hand("mere pati ne mujhe maara, september 2024 mein. kaunsi dhara lagegi?", HINDI,
         date(2024, 9, 1), (*HURT, "498A")),
    Hand("तेज़ाब फेंकने की सज़ा क्या है?", HINDI, None, ("326A",)),
    Hand("dhokhadhadi ka case 2025 mein hua, kaunsa section lagega?", HINDI, date(2025, 1, 1),
         CHEATING),
    # Outside both codes. Section 138 is a real number in both, which is the trap.
    Hand("What is the punishment for a cheque bounce under section 138?", OUT),
    Hand("How do I file for divorce by mutual consent?", OUT),
    Hand("How do I apply for anticipatory bail?", OUT),
    Hand("What is the fine for riding without a helmet?", OUT),
    Hand("How much income tax do I pay on a salary of 12 lakh?", OUT),
    Hand("Can my landlord evict me without notice?", OUT),
    Hand("What is the capital of Australia?", OUT),
    Hand("Write me a poem about the monsoon.", OUT),
)


def _ids(act: Act, numbers: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{act}:{n}" for n in numbers)


def expand(hand: Hand, bundle: Bundle) -> Case:
    ipc = _ids(Act.IPC, hand.ipc)
    bns = _ids(Act.BNS, hand.bns) or tuple(
        sorted({b for i in ipc for b in bundle.replaced_by(i)}))
    act = hand.act or (act_in_force_on(hand.day) if hand.day else None)
    if hand.category is Category.OUT_OF_SCOPE:
        targets, wrong = (), ()
    elif act is Act.IPC:
        targets, wrong = ipc, bns
    elif act is Act.BNS:
        targets, wrong = bns, ipc
    else:
        targets, wrong = (*ipc, *bns), ()
    return Case(
        id=case_id(hand.category, hand.question), category=hand.category,
        question=hand.question, offence_date=hand.day, answer_act=act, targets=targets,
        wrong_regime=wrong,
        needs_clarification=act is None and hand.category is not Category.OUT_OF_SCOPE,
    )
