from typing import Optional, List

from ovos_plugin_manager.coreference import CoreferenceSolverEngine
from ovos_plugin_manager.templates.transformers import UtteranceTransformer

from ovos_coreferee.parser import CorefereeParser


class CorefereeSolver(CoreferenceSolverEngine):
    parser: CorefereeParser = None

    @classmethod
    def solve_corefs(cls, text, lang="en"):
        if cls.parser is None:
            cls.parser = CorefereeParser()
        return cls.parser.replace_corefs(text)


class CorefereeNormalizerPlugin(UtteranceTransformer):
    """plugin to normalize utterances by replacing coreferences
    this helps intent parsers"""

    def __init__(self, name="ovos-coreferee-normalizer", priority=1):
        super().__init__(name, priority)
        self.parser = CorefereeParser()

    def transform(self, utterances: List[str],
                  context: Optional[dict] = None) -> (list, dict):

        norm = []
        for u in utterances:
            norm.append(u)
            norm.append(self.parser.replace_corefs(u))

        # this deduplicates the list while keeping order
        return list(dict.fromkeys(norm)), context
