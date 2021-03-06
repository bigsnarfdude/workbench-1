
''' PE Classify worker (just a placeholder, not a real classifier at this point) '''

import json
import pymongo
import gridfs
import hashlib
import datetime

def plugin_info():
    return {'name':'pe_classifier', 'class':'PEFileClassify', 'dependencies': ['pe_features','pe_indicators'],
            'description': 'This worker classifies PEFiles as Evil or Benign. Output keys: [classification]'}

class PEFileClassify():

    def execute(self, input_data):

        # In general you'd do something different with these two outputs
        # for this toy example will just smash them in a big string
        pefile_output = input_data['pe_features']
        indicators = input_data['pe_indicators']
        all_input = str(pefile_output) + str(indicators)

        flag = 'Reported Checksum does not match actual checksum'
        if flag in all_input:
            return {'classification':'Evil!'}
        else:
            return {'classification':'Benign'}

# Unit test: Create the class, the proper input and run the execute() method for a test
def test():
    ''' pe_classifier.py: Unit test'''
    import pe_features
    input_worker = pe_features.PEFileWorker()
    _raw_output = input_worker.execute({'sample':{'raw_bytes':open('../../test_files/pe/bad/033d91aae8ad29ed9fbb858179271232', 'rb').read()}})
    wrapped_output = {'pe_features':_raw_output}


    import pe_indicators
    input_worker2 = pe_indicators.Indicators()
    _raw_output = input_worker2.execute({'sample':{'raw_bytes':open('../../test_files/pe/bad/033d91aae8ad29ed9fbb858179271232', 'rb').read()}})
    wrapped_output2 = {'pe_indicators':_raw_output}

    # Now join up the inputs
    wrapped_output.update(wrapped_output2)
    worker = PEFileClassify()
    print worker.execute(wrapped_output)

if __name__ == "__main__":
    test()