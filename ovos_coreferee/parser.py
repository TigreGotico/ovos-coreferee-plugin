from typing import Tuple, Dict, List

import spacy
from spacy.cli import download
from spacy.tokens import Token


class CorefereeParser:
    """Extract semantic triples for knowledge graph construction."""

    def __init__(self, model="en_core_web_trf",
                 first_person_token="SPEAKER") -> None:
        self.first_person = first_person_token
        """Load spaCy model."""
        if not spacy.util.is_package(model):
            download(model)
        if model == "en_core_web_trf":
            # EXTRA MODEL ALSO NEEDED
            if not spacy.util.is_package("en_core_web_lg"):
                download("en_core_web_lg")
        self.nlp = spacy.load(model)
        self.nlp.add_pipe("coreferee")

    def replace_corefs(self, text: str) -> str:
        doc = self.nlp(text)
        # debug print coref
        #doc._.coref_chains.print()

        mapping: Dict[int, str] = {}
        prev_propn = None
        for idx, tok in enumerate(doc):
            next_token = doc[idx+1] if idx < len(doc) - 1 else None
            if tok.pos_ == "PROPN":
                prev_propn = tok
            elif tok.pos_ == "PRON":
                if tok.text.lower() in ["me"]:
                    print(" -", idx, tok, "->", self.first_person)
                    mapping[idx] = self.first_person
                elif tok.text.lower() in ["i"]:
                    print(" -", idx, tok, "->", self.first_person)
                    mapping[idx] = self.first_person
                    if next_token.text == "have":
                        mapping[idx+1] = "has"
                    elif next_token.pos_ == "VERB" and next_token.text.endswith("e"):
                        mapping[idx+1] = next_token.text + "s"
                elif tok.text.lower() in ["my", "mine"]:
                    print(" -", idx, tok, "->", self.first_person + "'s")
                    mapping[idx] = self.first_person + "'s"
                elif tok.text.lower() in ["mine"]:
                    print(" -", idx, tok, "->", "belongs to " + self.first_person)
                    mapping[idx] = self.first_person
                    mapping[idx - 1] = "belongs to"
                elif tok.text.lower() in ["who"] and prev_propn:
                    print(" -", idx, tok, "->", prev_propn)
                    mapping[idx] = prev_propn.text
                elif tok.text.lower() in ["we"]:
                    nouns = [mapping.get(i) or tok.text
                             for i, tok in enumerate(doc[:idx])
                             if tok.pos_ in ['NOUN', 'PROPN', 'PRON']]
                    if len(nouns) > 2:
                        last = nouns[-1]
                        nouns = nouns[:-1]
                        plural = ", ".join(nouns) + " and " + last
                        print(" -", idx, tok, "->", plural)
                        mapping[idx] = plural
                    elif len(nouns) == 2:
                        plural = " and ".join(nouns)
                        print(" -", idx, tok, "->", plural)
                        mapping[idx] = plural

        for chain in doc._.coref_chains:
            plural = any(len(mention) > 1 for mention in chain.mentions)
            if plural:
                continue

            ctoks = []
            for m in chain.mentions:
                # filter pronouns from candidate replacements
                ctoks += [doc[i] for i in m.token_indexes if doc[i].pos_ in ['NOUN', 'PROPN']]
            if not ctoks:
                continue

            # pick the longest PROPER NOUN token
            propers = [tok for tok in ctoks if tok.pos_ == 'PROPN']
            if propers:
                resolve_tok = max(propers, key=lambda k: len(k.text))
            else:
                # let's just pick the longest NOUN token
                resolve_tok = max(ctoks, key=lambda k: len(k.text))

            for mention in chain.mentions:
                idx = mention[0]
                if resolve_tok.text == doc[idx].text:
                    continue
                print(" -", idx, doc[idx], "->", resolve_tok)
                mapping[idx] = resolve_tok.text

        for chain in doc._.coref_chains:
            plural = any(len(mention) > 1 for mention in chain.mentions)
            if plural:
                m = max(chain.mentions, key=len)
                joint_str = " and ".join([mapping.get(i) or doc[i].text for i in m])
                for mention in chain:
                    if len(mention) == 1:
                        idx = mention[0]
                        mapping[idx] = joint_str
                        print(" -", idx, doc[idx], "->", joint_str)

        tokens = [mapping.get(idx, t.text)
                  for idx, t in enumerate(doc)]
        return " ".join(tokens).replace(" , ", ", ").replace(" .", ".")


if __name__ == "__main__":
    coref = CorefereeParser(first_person_token="Miro")

    test = [
        "My name is Miro. I like beer",
        "Barrack Obama was born in Hawaii. He was president of the United States and lived in the White House.",
        "London has been a major settlement for two millennia. It was founded by the Romans, who named it Londinium.",
        "He was very busy with his work, Peter had had enough of it. He and his wife decided they needed a holiday. They travelled to Spain because they loved the country very much.",
        "My name is Miro. I like beer",
        "The ring belongs to me!",
        "The ring is mine! My birthday gift, my precious",
        "I love my baby",
        "I have a dog, a cat and a bird. we are a happy family",
        "My neighbors have a cat. It has a bushy tail",
        "My sister has a dog, She loves him!",
        "Here is the book now take it",
        "The sign was too far away for the boy to read it",
        "Dog is man's best friend. It is always loyal",
        "The girl said she would take the trash out",
        "I voted for Bob because he is clear about his values. His ideas represent a majority of the nation. He is better than Alice",
        "Jack von Doom is one of the top candidates in the elections. His ideas are unique compared to Bob's",
        "Members voted for John because they see him as a good leader",
        "Leaders around the world say they stand for peace",
        "My neighbours just adopted a puppy. They care for it like a baby",
        "I have many friends. They are an important part of my life",
        "is the light turned on? turn it off",
        "Turn off the light and change it to blue",
        "call Mom. tell her to buy eggs. tell her to buy coffee. tell her to buy milk",
        "call dad. tell him to buy bacon. tell him to buy coffee. tell him to buy beer",
        "Chris is very handsome. He is Australian. Elsa lives in Arendelle. He likes her.",
        "One night, Michael caught Tom in his office",
        "One night, Michael caught Tom breaking into his office",
        "Alice invited Marcia to go with her",
        "The Martians invited the Venusians to go with them to Pluto",
        "A short while later, Michael decided that he wanted to play a role in his son's life, and tried to get Lisa to marry him, but by this time, she wanted nothing to do with him. Around the same time, Lisa's son Tom had returned from Vietnam with a drug habit. One night, Michael caught Tom breaking into his office to steal drugs",
        "Kevin invited Bob to go with him to his favorite fishing spot",
        "Bob telephoned Jake to tell him that he lost the laptop.",
        "Ana telephoned Alice to tell her that she lost the bus",
        "The Martians told the Venusians that they used to have an ocean",
        "Joe was talking to Bob and told him to go home because he was drunk",
        "the dudes were talking with their enemies and they decided to avoid war",
        "Janet has a husband, Sproule, and one son, Sam. A second child was stillborn in November 2009, causing her to miss Bristol City's match against Nottingham Forest. City manager Gary Johnson dedicated their equalising goal in the match to Janet, who had sent a message of support to her teammates.",
        "Sproule has a wife, Janet, and one son, Sam. A second child was stillborn in November 2009, causing him to miss Bristol City's match against Nottingham Forest. City manager Gary Johnson dedicated their equalising goal in the match to Sproule, who had sent a message of support to his teammates.",
        "Bob threatened to kill Alice to make her pay her debts",
        "Alice invited Marcia to go with her to their favorite store",
        "Adriana said she loves me!"

    ]
    for t in test:
        print(t)
        print("     ", coref.replace_corefs(t))
        # My name is Miro. I like beer
        #  - 0 My -> Miro's
        #  - 5 I -> Miro
        #       Miro's name is Miro. Miro likes beer

        # Barrack Obama was born in Hawaii. He was president of the United States and lived in the White House.
        #  - 7 He -> Obama
        #       Barrack Obama was born in Hawaii. Obama was president of the United States and lived in the White House.

        # London has been a major settlement for two millennia. It was founded by the Romans, who named it Londinium.
        #  - 17 who -> Romans
        #  - 10 It -> settlement
        #  - 19 it -> settlement
        #       London has been a major settlement for two millennia. settlement was founded by the Romans, Romans named settlement Londinium.

        # He was very busy with his work, Peter had had enough of it. He and his wife decided they needed a holiday. They travelled to Spain because they loved the country very much.
        #  - 13 it -> work
        #  - 15 He -> Peter
        #  - 17 his -> Peter
        #  - 33 country -> Spain
        #  - 20 they -> Peter and wife
        #  - 25 They -> Peter and wife
        #  - 30 they -> Peter and wife
        #       He was very busy with his work, Peter had had enough of work. Peter and Peter wife decided Peter and wife needed a holiday. Peter and wife travelled to Spain because Peter and wife loved the Spain very much.

        # My name is Miro. I like beer
        #  - 0 My -> Miro's
        #  - 5 I -> Miro
        #       Miro's name is Miro. Miro likes beer

        # The ring belongs to me!
        #  - 4 me -> Miro
        #       The ring belongs to Miro !

        # The ring is mine! My birthday gift, my precious
        #  - 3 mine -> Miro's
        #  - 5 My -> Miro's
        #  - 9 my -> Miro's
        #       The ring is Miro's ! Miro's birthday gift, Miro's precious

        # I love my baby
        #  - 0 I -> Miro
        #  - 2 my -> Miro's
        #       Miro loves Miro's baby

        # I have a dog, a cat and a bird. we are a happy family
        #  - 0 I -> Miro
        #  - 11 we -> Miro, dog, cat and bird
        #       Miro has a dog, a cat and a bird. Miro, dog, cat and bird are a happy family
