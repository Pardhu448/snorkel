import os
import numpy as np

from snorkel.parser import ImageCorpusExtractor, CocoPreprocessor
from snorkel.models import StableLabel
from snorkel.db_helpers import reload_annotator_labels

from snorkel.contrib.babble import Babbler
from snorkel.contrib.babble.pipelines import BabblePipeline

from tutorials.babble import MTurkHelper


class BikePipeline(BabblePipeline):

    def parse(self, anns_path=os.environ['SNORKELHOME'] + '/tutorials/babble/bike/data/'):
        self.anns_path = anns_path
        train_path = anns_path + 'train_anns.npy'
        val_path = anns_path + 'val_anns.npy'

        corpus_extractor = ImageCorpusExtractor(candidate_class=self.candidate_class)

        coco_preprocessor = CocoPreprocessor(train_path, source=0)
        corpus_extractor.apply(coco_preprocessor)

        coco_preprocessor = CocoPreprocessor(val_path, source=1)
        corpus_extractor.apply(coco_preprocessor, clear=False)


    def extract(self):
        print("Extraction was performed during parse stage.")
        for split in self.config['splits']:
            num_candidates = self.session.query(self.candidate_class).filter(
                self.candidate_class.split == split).count()
            print("Candidates [Split {}]: {}".format(split, num_candidates))

    def load_gold(self, anns_path=None, annotator_name='gold'):
        if anns_path:
            self.anns_path = anns_path
            
        def load_labels(set_name, output_csv_path):
            helper = MTurkHelper(candidates=[], labels=[], num_hits=None, domain='vg', workers_per_hit=3)
            labels_by_candidate = helper.postprocess_visual(output_csv_path, 
                                                            is_gold=True, set_name=set_name, 
                                                            candidates=[], verbose=False)
            return labels_by_candidate
            
        
        validation_labels_by_candidate = load_labels('val', self.anns_path+
                                                     'Labels_for_Visual_Genome_all_out.csv')
        train_labels_by_candidate = load_labels('train', self.anns_path+
                                                'Train_Labels_for_Visual_Genome_out.csv')

        def assign_gold_labels(labels_by_candidate):
            for candidate_hash, label in labels_by_candidate.items():
                set_name, image_idx, bbox1_idx, bbox2_idx = candidate_hash.split(':')
                source = {'train': 0, 'val': 1}[set_name]
                stable_id_1 = "{}:{}::bbox:{}".format(source, image_idx, bbox1_idx)
                stable_id_2 = "{}:{}::bbox:{}".format(source, image_idx, bbox2_idx)
                context_stable_ids = "~~".join([stable_id_1, stable_id_2])
                query = self.session.query(StableLabel).filter(StableLabel.context_stable_ids == context_stable_ids)
                query = query.filter(StableLabel.annotator_name == annotator_name)
                label = 1 if label else -1
                if query.count() == 0:
                    self.session.add(StableLabel(
                        context_stable_ids=context_stable_ids,
                        annotator_name=annotator_name,
                        value=label))

            self.session.commit()
            reload_annotator_labels(self.session, self.candidate_class, 
                annotator_name, split=source, filter_label_split=False)
            
            
        assign_gold_labels(validation_labels_by_candidate)
        assign_gold_labels(train_labels_by_candidate)

    def collect(self):
        helper = MTurkHelper()
        output_csv_path = (os.environ['SNORKELHOME'] + 
                        '/tutorials/babble/bike/data/VisualGenome_all_out.csv')
        explanations = helper.postprocess_visual(output_csv_path, set_name='train', verbose=False)
        
        from snorkel.contrib.babble import link_explanation_candidates
        candidates = self.session.query(self.candidate_class).filter(self.candidate_class.split == self.config['babbler_candidate_split']).all()
        explanations = link_explanation_candidates(explanations, candidates)
        user_lists = {}
        super(BikePipeline, self).babble('image', explanations, user_lists, self.config)