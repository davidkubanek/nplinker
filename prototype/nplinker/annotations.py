import os
import csv

from .logconfig import LogConfig
logger = LogConfig.getLogger(__file__)

GNPS_KEY = 'gnps'
GNPS_URL_FORMAT = 'https://metabolomics-usi.ucsd.edu/{}/?usi=mzspec:GNPSLIBRARY:{}'
GNPS_INDEX_COLUMN = '#Scan#'
GNPS_DATA_COLUMNS = ['Compound_Name', 'Organism', 'MQScore', 'SpectrumID']

def headers_match_gnps(headers):
    for k in GNPS_DATA_COLUMNS:
        if k not in headers:
            return False
    return True

    @property
    def png_url(self):
        return self.PLOT_URL.format('png', self.id)

    @property
    def svg_url(self):
        return self.PLOT_URL.format('svg', self.id)

    @property
    def spec_url(self):
        return self.PLOT_URL.format('spectrum', self.id)

    @property
    def json_url(self):
        return self.PLOT_URL.format('json', self.id)

def load_annotations(root, config, spectra, spec_dict):
    if not os.path.exists(root):
        logger.debug('Annotation directory not found ({})'.format(root))
        return spectra

    ac = {}
    if os.path.exists(config):
        # parse annotations config file if it exists
        with open(config, 'r') as f:
            rdr = csv.reader(f, delimiter='\t')
            for row in rdr:
                # expecting 3 columns: filename, index col name, data col name(s)
                if len(row) != 3:
                    logger.warning('Malformed line in annotations configuration: {}'.format(row))
                    continue
                # record the columns with filename as key
                data_cols = row[2].split(',')
                if len(data_cols) == 0:
                    logger.warning('No data columns selected in annotation file {}, skipping it!'.format(row[0]))
                    continue
                ac[row[0]] = (row[1], data_cols)

    logger.debug('Parsed {} annotations configuration entries'.format(len(ac)))

    annotation_files = []
    for f in os.listdir(root):
        if f == os.path.split(config)[1] or not f.endswith('.tsv'):
            continue
        annotation_files.append(os.path.join(root, f))

    logger.debug('Found {} annotations .tsv files in {}'.format(len(annotation_files), root))
    for af in annotation_files:
        with open(af, 'r') as f:
            rdr = csv.reader(f, delimiter='\t')
            headers = next(rdr)
            filename = os.path.split(af)[1]

            if headers_match_gnps(headers):
                # assume this is our main annotations file
                logger.debug('Parsing GNPS annotations from {}'.format(af))

                scans_index = headers.index(GNPS_INDEX_COLUMN)

                for line in rdr:
                    # read the scan ID column and get the corresponding Spectrum object
                    scan_id = int(line[scans_index])
                    if scan_id not in spec_dict:
                        logger.warning('Unknown spectrum ID found in GNPS annotation file (ID={})'.format(scan_id))
                        continue

                    spec = spec_dict[scan_id]
                    data_cols = set(GNPS_DATA_COLUMNS)
                    # merge in any extra columns the user has provided
                    if filename in ac:
                        data_cols.update(ac[filename][1])

                    data = {}
                    for dc in data_cols:
                        if dc not in headers:
                            logger.warning('Column lookup failed for "{}"'.format(dc))
                            continue
                        data[dc] = line[headers.index(dc)]

                    # also insert useful URLs
                    for t in ['png', 'json', 'svg', 'spectrum']:
                        data['{}_url'.format(t)] = GNPS_URL_FORMAT.format(t, data['SpectrumID'])
                    # TODO will there only ever be a single entry here?
                    spec.add_annotations(GNPS_KEY, data)
                    print(spec)
            else:
                logger.debug('Parsing general annotations from {}'.format(af))
                # this is a general annotations file, so rely purely on the user-provided columns
                index_col, data_cols = ac[filename]
                if index_col not in headers:
                    raise Exception('Annotation index column "{}" not found in file "{}"!'.format(index_col, filename))

                spec_id_index = headers.index(index_col)

                for line in rdr:
                    scan_id = int(line[spec_id_index])
                    if scan_id not in spec_dict:
                        logger.warning('Unknown spectrum ID found in annotation file "{}", ID is "{}"'.format(filename, scan_id))
                        continue

                    spec = spec_dict[scan_id]
                    data = {}
                    for dc in data_cols:
                        if dc not in headers:
                            logger.warning('Column lookup failed for "{}"'.format(dc))
                            continue
                        data[dc] = line[headers.index(dc)]

                    spec.append_annotations(filename, data)

    return spectra

