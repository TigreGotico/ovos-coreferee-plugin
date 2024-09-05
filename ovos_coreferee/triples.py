from typing import Tuple, Dict, List, Iterable

import spacy
from spacy.cli import download
from spacy.tokens import Token

from ovos_coreferee.parser import CorefereeParser
try:
    from ovos_plugin_manager.templates.triples import TriplesExtractor
except ImportError:  # needs https://github.com/OpenVoiceOS/ovos-plugin-manager/pull/257
    class TriplesExtractor:

        def __init__(self, config=None):
            self.config = config or {}
            self.first_person_token = self.config.get("first_person_token", "USER")

        def extract_triples(self, documents: List[str]) -> Iterable[Tuple[str, str, str]]:
            """Extract semantic triples from a list of documents."""


class DependencyParser:
    def __init__(self):
        self.NEGATION = {"no", "not", "n't", "never", "none"}
        self.SUBJECTS = {"nsubj", "nsubjpass", "csubj", "csubjpass", "agent", "expl"}
        self.OBJECTS = {"dobj", "dative", "attr", "oprd", "pobj"}

    def extract_NER_preps(self, doc):
        triples = []
        # TODO - "Barrack Obama was born in Hawaii. Obama was president of the United States and lived in the White House.",
        # missing (Obama, lived in, the White House)

        # TODO - ('obama', 'be', 'president') should be ('obama', 'be', 'president of the United States')
        for ent in doc.ents:
            if len(ent) > 1:  # Check if it's a multi-word entity
                ent_text = " ".join([t.text for t in ent])
            else:
                ent_text = ent.text

            preps = [prep for prep in ent.root.head.children if prep.dep_ == "prep"]
            for prep in preps:
                for child in prep.children:
                    triples.append((ent_text, "{} {}".format(ent.root.head, prep), child.text))
        return triples

    def get_subs_from_conjunctions(self, subs: List[Token]) -> List[Token]:
        more_subs = []
        for sub in subs:
            if "and" in {tok.lower_ for tok in sub.rights}:
                more_subs.extend([tok for tok in sub.rights if tok.dep_ in self.SUBJECTS or tok.pos_ == "NOUN"])
                more_subs.extend(self.get_subs_from_conjunctions(
                    [tok for tok in sub.rights if tok.dep_ in self.SUBJECTS or tok.pos_ == "NOUN"]))
        return more_subs

    def get_objs_from_conjunctions(self, objs: List[Token]) -> List[Token]:
        more_objs = []
        for obj in objs:
            if "and" in {tok.lower_ for tok in obj.rights}:
                more_objs.extend([tok for tok in obj.rights if tok.dep_ in self.OBJECTS or tok.pos_ == "NOUN"])
                more_objs.extend(self.get_objs_from_conjunctions(more_objs))
        return more_objs

    def is_negated(self, tok: Token) -> bool:
        return any(dep.lower_ in self.NEGATION for dep in tok.children)

    def find_svos(self, tokens: List[Token]) -> List[Tuple[str, str, str]]:
        svos = []

        verbs = [(idx, tok) for idx, tok in enumerate(tokens) if tok.pos_ in ["VERB", "AUX"]]
        for idx, v in verbs:
            nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
            subs, verb_negated = self.get_all_subs(v)

            _, objs = self.get_all_objs(v)

            # Handle copular constructions
            if v.lemma_ in {"be"}:
                cop_svos = self.handle_copular_constructions(v, subs)
                if cop_svos:
                    svos.extend(cop_svos)
                continue

            # General cases
            for sub in subs:
                objs = [tok for tok in v.rights if tok.dep_ in self.OBJECTS]
                objs.extend(self.get_objs_from_conjunctions(objs))
                for obj in objs:
                    obj_negated = self.is_negated(obj)
                    svos.append((
                        sub.text,
                        "!" if verb_negated or obj_negated else "" + (
                            v.lemma_ + " " + nxt.text
                            if nxt is not None and nxt.dep_ == "prep" else v.lemma_),
                        obj.text
                    ))

            if not subs:
                subject = None
                # Find subject in the lefts of the verb (typically where subjects appear)
                for tok in tokens[:idx + 1]:
                    if tok.dep_ in self.SUBJECTS:
                        subject = tok
                if subject:
                    # Find object in the right of the verb (typically where objects appear)
                    if not objs and nxt is not None:
                        if nxt.dep_ in ["ROOT"]:
                            continue

                        for idx2, tok in enumerate(tokens[idx:]):
                            prev = tokens[idx + idx2 - 1] if idx2 > 0 else None
                            if tok.dep_ in self.OBJECTS:
                                if prev.dep_ in ["compound"]:
                                    obj = tokens[idx + idx2 - 1: idx + idx2 + 1]
                                else:
                                    obj = tok
                                svos.append((
                                    subject.text,
                                    v.lemma_ + " " + nxt.text if nxt.dep_ == "prep" else v.lemma_,
                                    obj.text
                                ))
                                objs.append(obj)
                                break

                    subs.append(subject)

        return svos

    def get_all_subs(self, v: Token) -> Tuple[List[Token], bool]:
        verb_negated = self.is_negated(v)
        subs = [tok for tok in v.lefts if tok.dep_ in self.SUBJECTS]
        if subs:
            subs.extend(self.get_subs_from_conjunctions(subs))
        return subs, verb_negated

    def get_all_objs(self, v: Token) -> Tuple[Token, List[Token]]:
        objs = [tok for tok in v.rights if tok.dep_ in self.OBJECTS]
        objs.extend(self.get_objs_from_conjunctions(objs))
        return v, objs

    def handle_copular_constructions(self, v: Token, subs: List[Token]) -> List[Tuple[str, str, str]]:
        svos = []
        for sub in subs:
            objs = [tok for tok in v.rights if tok.dep_ in {"attr", "acomp", "pobj"}]
            for obj in objs:
                svos.append((sub.text, v.lemma_, obj.text))
        return svos


class SpacyTriplesExtractor(TriplesExtractor):
    """Extract semantic triples for knowledge graph construction."""

    def __init__(self, config: Dict) -> None:
        super().__init__(config)

        model = self.config.get("model", "en_core_web_trf")
        solve_coref = self.config.get("solve_coref", True)

        if not spacy.util.is_package(model):
            download(model)
        if solve_coref:
            self.coref = CorefereeParser(first_person_token=self.first_person_token,
                                         model=model)
            self.nlp = self.coref.nlp
        else:
            self.nlp = spacy.load(model)

        if self.config.get("spotlight"):
            try:
                self.nlp.add_pipe('dbpedia_spotlight')
            except Exception as e:
                print("WARNING - dbpedia spotlight not available! "
                      "pip install 'spacy_dbpedia_spotlight'")

    def extract_triples(self, documents: List[str]) -> Iterable[Tuple[str, str, str]]:
        """Extract semantic triples from a list of documents."""
        parser = DependencyParser()

        for idx, text in enumerate(documents):
            if text:
                if self.coref is not None:
                    #print(text)
                    text = self.coref.replace_corefs(text, join_tok=" and ")
                    #print("COREF SOLVED:", text)
                doc = self.nlp(text)
                # print([(tok, tok.pos_) for tok in doc])
                for t in parser.extract_NER_preps(doc):
                    yield t
                for t in parser.find_svos(doc):
                    yield t


if __name__ == "__main__":
    extractor = SpacyTriplesExtractor({"model": "en_core_web_trf",
                                       "spotlight": True,
                                       "first_person_token": "Miro"})

    test = [
        "Miro loves Dii.",
        "Miro has a dog.",
        "Miro is a software developer.",
        "beer is nice",
        "My name is Miro. I like beer",
        "Mike is a nice guy",
        "Chris was an asshole",
        "Apple was founded in Cupertino in the year 1981.",
        "Barrack Obama was born in Hawaii. He was president of the United States and lived in the White House.",
        "London has been a major settlement for two millennia. It was founded by the Romans, who named it Londinium.",
        "He was very busy with his work, Peter had had enough of it. He and his wife decided they needed a holiday. They travelled to Spain because they loved the country very much.",
        "My name is Miro. I like beer",
        "The ring belongs to me!",
        "The ring is mine! My birthday gift, my precious",
        "I love my baby",
        "I have a dog, a cat and a bird. we are a happy family",
        "Does Bob like coding? Yes he does"
    ]

    for triple in extractor.extract_triples(test):
        print(triple)
        # ('Miro', 'love', 'Dii')
        # ('Miro', 'have', 'dog')
        # ('Miro', 'be', 'developer')
        # ('beer', 'be', 'nice')
        # ('name', 'be', 'Miro')
        # ('Miro', 'like', 'beer')
        # ('Mike', 'be', 'guy')
        # ('Chris', 'be', 'asshole')
        # ('Apple', 'founded in', 'Cupertino')
        # ('Apple', 'founded in', 'year')
        # ('Barrack Obama', 'born in', 'Hawaii')
        # ('Obama', 'be', 'president')
        # ('Obama', 'live in', 'White House')
        # ('London', 'been for', 'millennia')
        # ('London', 'be', 'settlement')
        # ('Romans', 'name', 'settlement')
        # ('Romans', 'name', 'Londinium')
        # ('Peter', 'travelled to', 'Spain')
        # ('He', 'be', 'busy')
        # ('Peter', 'have', 'enough')
        # ('Peter', 'need', 'holiday')
        # ('wife', 'need', 'holiday')
        # ('Peter', 'love', 'Spain')
        # ('wife', 'love', 'Spain')
        # ('name', 'be', 'Miro')
        # ('Miro', 'like', 'beer')
        # ('ring', 'be', 'Miro')
        # ('Miro', 'love', 'baby')
        # ('Miro', 'have', 'dog')
        # ('Miro', 'be', 'family')
        # ('dog', 'be', 'family')
        # ('cat', 'be', 'family')
        # ('bird', 'be', 'family')
        # ('Bob', 'like', 'coding')

