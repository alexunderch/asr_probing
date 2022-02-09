from constants import Constants
from func_utils import print_if_debug, label_batch

from torchaudio import load, transforms
from datasets import load_dataset, load_from_disk
from transformers import BertTokenizer
from datasets import Dataset, DatasetDict
from collections import Callable
import json
import pandas as pd
import numpy as np

modes = ['word_detail', 'phonetic_detail']
class LinguisticDataset:
    def __init__(self, mode: str, save_path: str = None):
        """Linguistic dataset wrapper for TIMIT_ASR dataset
        Args:
             mode, str: 'word_detail' or 'phonetic_detail'
             save_path, str: optional way to save probing data, active only if save_outputs = True;
                            default = None
        """
        assert mode in ['word_detail', 'phonetic_detail']
        self.mode = mode
        self.save_path = save_path
        self.D = load_dataset('timit_asr', split = 'test')
        self.data = []
    def format_dataset(self):
        """Making JSON for TIMIT_ASR dataset
        """
        def process_fn(batch):
            data = {'long': []}

            for i in range(len(batch[self.mode]['start'])): data['long'].append((batch[self.mode]['start'][i], 
                                                                                  batch[self.mode]['stop'][i]))
            data['path'] = batch['file']
            data['utterance'] = batch[self.mode]['utterance']
            return data
        print_if_debug('making json...', Constants.DEBUG)
        for batch in self.D: self.data.append(process_fn(batch)) 
        if self.save_path is not None: assert isinstance(self.save_path, str)
        else: self.save_path = '.'   
        with open(self.save_path + 'timit_'+ self.mode +'.json', 'w') as fout: json.dump(self.data, fout)

    def __call__(self, additional_preprocessing: Callable = None, debug: bool = False, take_n: int = None) -> Dataset:
        """
        Args:
            additional_preprocessing, callable object: function to make new labels from phonemes, eg. POS-tags
                                                      default  = None, 
            debug, bool: flag, default = False
            take_n, int: how many samples from original set to take
                        default   = 10000 (None)
        Returns: new Hugging Face dataset
        """
        self.format_dataset()
        dataset = Dataset.from_pandas(pd.read_json(self.save_path + 'timit_'+ self.mode +'.json'))
        def mapping_fn(batch):
            """Phonemes mapping
            """
            speech_array, sampling_rate = load(batch["path"])
            resampler = transforms.Resample(sampling_rate, 16000)
            batch["speech"] = speech_array.squeeze().numpy()
            batch['atoms'] = []
            for l in batch['long']: 
                batch['atoms'].append(batch['speech'][l[0]:l[1]])
            return batch

        dataset = dataset.map(mapping_fn)
        new_data = []
        for example in dataset:
            for ind in range(len(example['atoms'])):
              if  len(example['atoms'][ind]) > 0 and \
                  len(example['atoms'][ind]) <= Constants.MAX_LEN if self.mode == 'word_detail' else int(0.01 * Constants.MAX_LEN): 

                  new_data.append([example['atoms'][ind], 16000,
                                   len(example['atoms'][ind]),
                                   example['utterance'][ind]])

              else: print_if_debug(example['utterance'][ind] + " " + "{}".format(len(example['atoms'][ind])), debug)
        new_dataset = pd.DataFrame(new_data, columns = ['speech', 'sampling_rate', 'len_speech', 'utterance'])

        if take_n is not None: 
            assert isinstance(take_n, int)
            print_if_debug("taking a slice of {} elements".format(take_n), debug)
            new_dataset = new_dataset.sample(n = take_n, random_state = 42)

        new_dataset =  Dataset.from_pandas(new_dataset)
        if additional_preprocessing is not None:
            assert isinstance(additional_preprocessing, type(lambda x: None))
            print_if_debug("adding new features...", debug)
            new_dataset = new_dataset.map(additional_preprocessing, batched = False)
        return new_dataset

class BertProbingDataset:
    def __init__(self, model_path: str, filepath: str, dataset_name: str, feature_column: str):
        self.fpath = filepath
        self.dname = dataset_name
        self.feature_column = feature_column
        self.tokenizer = BertTokenizer.from_pretrained(Constants.MODELS_PATH[model_path]["None"])
        self.maxlen = 0 
    def loadFile(self):
        import io
        self.task_data = {'train': {'data': [], self.feature_column: []},
                              'dev': {'data': [], self.feature_column: []},
                              'test': {'data': [], self.feature_column: []}}
        tok2split = {'tr': 'train', 'va': 'dev', 'te': 'test'}
        with io.open(self.fpath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip().split('\t')
                text = line[-1].split()
                self.maxlen = max(len(text), self.maxlen)

                self.task_data[tok2split[line[0]]]['data'].append(" ".join(text))
                self.task_data[tok2split[line[0]]][self.feature_column].append(line[1])

        labels = sorted(np.unique(self.task_data['train'][self.feature_column]))
        self.tok2label = dict(zip(labels, range(len(labels))))
        nclasses = len(self.tok2label)

        for split in self.task_data:
            for i, y in enumerate(self.task_data[split][self.feature_column]):
                self.task_data[split][self.feature_column][i] = self.tok2label[y]
    
    def make_dataset(self, from_disk = False, data_col: str = 'data'):
        ###TODO: ADD SUPPORT OF OTHER DATASET TYPES, DOCSTRINGS
        self.loadFile()
        def mapping_fn(batch, maxlen: int, data_col: str = 'data'):
            """BERT preprocessing
            """
            inputs = self.tokenizer(batch[data_col], return_tensors = 'pt',  
                                    max_length = maxlen, truncation = True, padding = 'max_length')
            batch['input_values'] = inputs.input_ids
            batch['attention_mask'] = inputs.attention_mask
            batch['label'] = int(batch[self.feature_column])
            return batch
        dataset = DatasetDict()
        for k, v in self.task_data.items(): 
            dataset[k] = Dataset.from_dict(v)
            dataset[k] = dataset[k].map(mapping_fn, fn_kwargs = {'maxlen': self.maxlen, 'data_col': data_col} )
        dataset.set_format(type = 'torch', columns = ['input_values', 'attention_mask', 'label'])
        dataset.save_to_disk(self.dname)
        return dataset

def make_dataset() -> DatasetDict:
    lingusitic_dataset = DatasetDict()
    for mode in modes:
        lingusitic_dataset[mode] = LinguisticDataset(mode, 
                                                    save_path = ".")(
                                                    label_batch if mode == 'word_detail' else None,
                                                    debug = Constants.DEBUG,
                                                    take_n = None if mode == 'word_detail' else 15000 )
    return lingusitic_dataset