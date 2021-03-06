
''' view_meta worker '''

def plugin_info():
    return {'name':'view_meta', 'class':'ViewMetaData', 'dependencies': ['meta'],
            'description': 'This worker generates a view for meta about a sample. Output keys: [mime_type, encoding, import_time, ssdeep, entropy, file_size]'}

class ViewMetaData():
    ''' ViewMetaData: Generates a view for meta data on the sample '''
    def execute(self, input_data):

        # Deprecation unless something more interesting happens with this class
        return input_data['meta']

# Unit test: Create the class, the proper input and run the execute() method for a test
def test():
    ''' view_meta.py: Unit test'''
    # This worker test requires a local server as it relies on the recursive dependencies
    import zerorpc
    c = zerorpc.Client()
    c.connect("tcp://127.0.0.1:4242")
    md5 = c.store_sample('bad_067b39', open('../../test_files/pdf/bad/067b3929f096768e864f6a04f04d4e54', 'rb').read(), 'pdf')
    output = c.work_request('view_meta', md5)
    print 'ViewMetaData: '
    import pprint
    pprint.pprint(output)

if __name__ == "__main__":
    test()