from grammar import Grammar
from snorkel_grammar import snorkel_rules, snorkel_ops, sem_to_str
from annotator import *

from pandas import DataFrame, Series

class Explanation(object):
    def __init__(self, condition, label, candidate=None, name=None, 
                 semantics=None, paraphrase=None):
        """
        Constructs an Explanation object.

        :param condition: A string explanation that expresses a Boolean 
            condition (e.g., "The sentence is at least 5 words long.")
        :param label: The label {-1, 1} to apply to candidates for which the 
            condition evaluates to True.
        :param candidate: A candidate that the explanation is consistent with.
        :param name: The name of this explanation.
        :param semantics: The intended semantic representation of the 
            explanation (if known).
        :param paraphrase: A paraphrase of the explanation.
        """
        assert(isinstance(condition, basestring))
        self.condition = condition
        assert(label in [-1, 1])
        self.label = label
        self.candidate = candidate
        self.name = name
        self.semantics = semantics
        self.paraphrase = paraphrase

    def __str__(self):
        if self.name:
            return 'Explanation("%s: %s, %s")' % (self.name, self.label, self.condition)
        else:
            return 'Explanation("%s, %s")' % (self.label, self.condition)
    
    def display(self):
        print 'Explanation'
        print('%-12s %s' % ('condition', self.condition))
        print('%-12s %d' % ('label', self.label))
        print('%-12s %s' % ('candidate', self.candidate))
        print('%-12s %s' % ('name', self.name))
        print('%-12s %s' % ('semantics', self.semantics))


class SemanticParser():
    def __init__(self, candidate_class, user_lists={}, beam_width=None, top_k=None):
        annotators = [TokenAnnotator(), PunctuationAnnotator(), IntegerAnnotator()]
        self.grammar = Grammar(rules=snorkel_rules, 
                               ops=snorkel_ops, 
                               candidate_class=candidate_class,
                               annotators=annotators,
                               user_lists=user_lists,
                               beam_width=beam_width,
                               top_k=top_k)
        self.explanation_counter = 0
        self.LFs = tuple([None] * 6)

    def preprocess(self, string):
        return string.replace("'", '"')

    def parse(self, explanations, names=None, verbose=False, return_parses=False):
        """
        Converts Explanation objects into labeling functions.

        :param explanations: An instance or list of Explanation objects
        """
        LFs = []
        parses = []
        explanations = explanations if isinstance(explanations, list) else [explanations]
        names = names if isinstance(names, list) else [names]
        for i, exp in enumerate(explanations):
            exp.condition = self.preprocess(exp.condition)
            rule = 'Label {} if {}'.format(exp.label, exp.condition)
            exp_parses = self.grammar.parse_string(rule)
            for j, parse in enumerate(exp_parses):
                # print(parse.semantics)
                lf = self.grammar.evaluate(parse)
                if return_parses:
                    parse.function = lf
                    parses.append(parse)
                if len(names) > i and names[i]:
                    lf.__name__ = "{}_{}".format(names[i], j)
                else:
                    lf.__name__ = "exp{}_{}".format(self.explanation_counter, j)
                LFs.append(lf)
            self.explanation_counter += 1
        if return_parses:
            if verbose:
                print("{} parses created from {} explanations".format(len(LFs), len(explanations)))
            return parses
        else:
            if verbose:
                print("{} LFs created from {} explanations".format(len(LFs), len(explanations)))
            return LFs

    def parse_and_evaluate(self, 
                           explanations, 
                           show_everything=False,
                           show_nothing=False,
                           show_explanation=False, 
                           show_candidate=False,
                           show_sentence=False, 
                           show_parse=False,
                           show_semantics=False,
                           show_correct=False,
                           show_passing=False, 
                           show_failing=False,
                           show_redundant=False,
                           show_erroring=False,
                           show_unknown=False,
                           pseudo_python=False,
                           remove_paren=False,
                           paraphrases=False,
                           only=[]):
        """
        Calls SemanticParser.parse and evaluates the accuracy of resulting LFs.
        
        Results are stored in self.results, which contains a pandas DataFrame.
        """
        assert(not (show_everything and show_nothing))
        if show_everything:
            if any([show_explanation, show_candidate, show_sentence, show_parse, show_semantics]):
                print("Note: show_everything = True. This overrides all other show_x commands.")
            show_explanation = show_candidate = show_sentence = show_parse = show_semantics = True
        if show_semantics:
            show_correct = show_passing = show_failing = True
            show_redundant = show_erroring = show_unknown = True
        if show_nothing:
            if any([show_explanation, show_candidate, show_sentence, show_parse, show_semantics, 
            show_correct, show_passing, show_failing, show_redundant, show_erroring, show_unknown]):
                print("Note: show_nothing = True. This will override all other show_ commands.")
            show_explanation = show_candidate = show_sentence = show_parse = show_semantics = False
            show_correct = show_passing = show_failing = show_redundant = show_erroring = show_unknown = False
        self.explanation_counter = 0
        explanations = explanations if isinstance(explanations, list) else [explanations]
        col_names = ['Correct', 'Passing', 'Failing', 'Redundant', 'Erroring', 'Unknown','Index']
        d = {}
        explanation_names = []
        indices = []

        nCorrect = [0] * len(explanations)
        nPassing = [0] * len(explanations)
        nFailing = [0] * len(explanations)
        nRedundant = [0] * len(explanations)
        nErroring = [0] * len(explanations)
        nUnknown = [0] * len(explanations)

        LFs = {
            'correct'  : [],
            'passing'  : [],
            'failing'  : [],
            'redundant': [],
            'erroring' : [],
            'unknown'  : [],
        }
        
        for i, explanation in enumerate(explanations):
            if only and i not in only:
                continue
            indices.append(i)
            if paraphrases and not explanation.paraphrase:
                raise Exception('Keyword argument paraphrases == True '
                                'but explanation has no paraphrase.')
            # TODO: remove remove_paren keyword and code
            if remove_paren:
                condition = explanation.replace('(', '')
                condition = explanation.replace(')', '')
            if show_explanation: 
                print("Explanation {}: {}\n".format(i, explanation))
            if show_candidate:
                print("CANDIDATE: {}\n".format(explanation.candidate))
            if show_sentence and not isinstance(explanation.candidate[0], str):
                print("SENTENCE: {}\n".format(explanation.candidate[0].get_parent()._asdict()['text']))
            semantics = set()
            parses = self.parse(
                        explanation, 
                        explanation.name,
                        return_parses=True)
            for parse in parses:
                if show_parse:
                    print("PARSE: {}\n".format(parse))
                semantics_ = sem_to_str(parse.semantics) if pseudo_python else parse.semantics
                # REDUNDANT
                if parse.semantics in semantics:
                    if show_redundant: print("R: {}\n".format(semantics_))
                    nRedundant[i] += 1
                    LFs['redundant'].append(parse.function)
                    continue
                semantics.add(parse.semantics)
                # ERRORING
                try:
                    label = parse.function(explanation.candidate)
                except:
                    if show_erroring: 
                        print("E: {}\n".format(semantics_))
                        print parse.semantics
                        print parse.function(explanation.candidate) #to display traceback
                        import pdb; pdb.set_trace()
                    nErroring[i] += 1 
                    LFs['erroring'].append(parse.function)
                    continue
                # CORRECT             
                if explanation.semantics and parse.semantics==explanation.semantics:
                    if show_correct: print("C: {}\n".format(semantics_))
                    nCorrect[i] += 1
                    LF = parse.function
                    LF.__name__ = LF.__name__[:(LF.__name__).rindex('_')] + '*'
                    LFs['correct'].append(parse.function)
                    continue
                # PASSING
                if label==explanation.label:
                    if show_passing: print("P: {}\n".format(semantics_))
                    nPassing[i] += 1
                    LFs['passing'].append(parse.function)
                    continue
                else:
                # FAILING
                    if show_failing: print("F: {}\n".format(semantics_))
                    nFailing[i] += 1
                    LFs['failing'].append(parse.function)
                    continue
                # UNKNOWN
                if explanation.candidate is None:
                    nUnknown[i] += 1
                    LFs['unknown'].append(parse.function)
                    continue
                raise Error('This should not be reached.')
                            
            if nCorrect[i] + nPassing[i] == 0:
                print("WARNING: No correct or passing parses found for the following explanation:")
                print("EXPLANATION {}: {}\n".format(i, explanation))

            if explanation.name:
                explanation_names.append(explanation.name)
            else:
                explanation_names.append("Explanation{}".format(i))

        d['Correct'] = Series(data=[nCorrect[i] for i in indices], index=explanation_names)
        d['Passing'] = Series(data=[nPassing[i] for i in indices], index=explanation_names)
        d['Failing'] = Series(data=[nFailing[i] for i in indices], index=explanation_names)
        d['Redundant'] = Series(data=[nRedundant[i] for i in indices], index=explanation_names)
        d['Erroring'] = Series(data=[nErroring[i] for i in indices], index=explanation_names)
        d['Unknown'] = Series(data=[nUnknown[i] for i in indices], index=explanation_names)
        d['Index'] = Series(data=indices, index=explanation_names)
        
        self.results = DataFrame(data=d, index=explanation_names)[col_names]
        return LFs