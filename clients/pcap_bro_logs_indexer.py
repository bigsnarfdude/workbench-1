
import zerorpc
import os
import pprint
import argparse

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=4242, help='port used by workbench server')
    parser.add_argument('-s', '--server', type=str, default='tcp://127.0.0.1', help='location of workbench server')
    args = parser.parse_args()
    port = str(args.port)
    server = str(args.server)
    c = zerorpc.Client(timeout=300)
    c.connect(server+':'+port)

    # Test out getting the raw Bro logs from a PCAP file and sending results to an ELS indexer
    file_list = [os.path.join('../test_files/pcap', child) for child in os.listdir('../test_files/pcap')]
    for filename in file_list:

        # Skip OS generated files
        if '.DS_Store' in filename: continue

        with open(filename,'rb') as file:
            md5 = c.store_sample(filename, file.read(), 'pcap')

            # Index the view_pcap_meta output (notice we can ask for any worker output)
            # Also (super important) it all happens on the server side.
            c.index_worker_output('view_pcap_bro', md5, 'pcap_bro')
            print '\n\n<<< PCAP Bro log Data: %s Indexed>>>' % (filename)

def test():
    ''' pcap_bro_logs_indexer test '''
    main()

if __name__ == '__main__':
    main()

