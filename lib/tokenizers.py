from transformers import BertTokenizer, Wav2Vec2Processor, T5Tokenizer
from base.processing import Processor

class BertProcessor(Processor):
    def __init__(self, model_path) -> None:
        super().__init__(tokenizer = BertTokenizer, model_path = model_path)
    def __call__(self, batch, max_len: int, data_column: str = "data"):
        """Preprocessing text features with padding to maximum lenght"""
        inputs = self.tokenizer(batch[data_column], return_tensors = 'pt',  
                                    max_length = max_len, truncation = True, padding = 'max_length')
        batch['input_values'] = inputs.input_ids
        batch['attention_mask'] = inputs.attention_mask
        return batch

class Wav2Vec2OProcessor(Processor):
    def __init__(self, model_path) -> None:
        super().__init__(tokenizer = Wav2Vec2Processor, model_path =  model_path)
    def __call__(self, batch, max_len: int, feature_column: str, data_column: str = "speech"):
        """Preprocessing audio features with padding to maximum lenght"""
        inputs = self.tokenizer(batch[data_column], sampling_rate = batch["sampling_rate"], return_tensors = "pt", 
                                padding = 'max_length', truncation = 'max_length', max_length = max_len)
        batch['input_values'] = inputs.input_values
        batch['attention_mask'] = inputs.attention_mask
        return batch

class T5Processor(Processor):
    def __init__(self, model_path: str) -> None:
        super().__init__(tokenizer = T5Tokenizer, model_path = model_path)
    def __call__(self, batch, max_len: int, data_column: str = "data"):
        """Preprocessing text features with padding to maximum lenght"""
        inputs = self.tokenizer(batch[data_column], return_tensors = 'pt',  
                                    max_length = max_len, truncation = True, padding = 'max_length')
        batch['input_values'] = inputs.input_ids
        batch['attention_mask'] = inputs.attention_mask
        return batch