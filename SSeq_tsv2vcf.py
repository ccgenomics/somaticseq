#!/usr/bin/env python3
# Try to implement custom combination of "MVJSDUL"

import sys, argparse, math, gzip


parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-tsv',   '--tsv-in', type=str, help='TSV in', required=True)
parser.add_argument('-vcf',   '--vcf-out', type=str, help='VCF iut', required=True)
parser.add_argument('-pass',  '--pass-threshold', type=str, help='Above which is automatically PASS', required=True)
parser.add_argument('-low',   '--lowqual-threshold', type=str, help='Low quality subject to lenient filter', required=True)
parser.add_argument('-all',   '--emit-all', action='store_true', help='Flag it to print out everything', required=False)
parser.add_argument('-phred', '--phred-scale', action='store_true', help='Flag it to print out Phred scale QUAL (proper VCF format but more annoying to filter)', required=False)

parser.add_argument('-tools', '--individual-mutation-tools',  type=str,   help='A list of all tools: have to match the annotated tool name in the input vcf files', nargs='*', required=False, default=('CGA', 'VarScan2', 'JointSNVMix2', 'SomaticSniper', 'VarDict', 'MuSE', 'LoFreq') )


args = parser.parse_args()

# Rename input:
tsv_fn = args.tsv_in
vcf_fn = args.vcf_out
tools = args.individual_mutation_tools
pass_score = float( args.pass_threshold )
lowqual_score = float( args.lowqual_threshold )

print_reject = args.emit_all
phred_scaled = args.phred_scale


tools_code = {'CGA':           'M',
              'VarScan2':      'V',
              'JointSNVMix2':  'J',
              'SomaticSniper': 'S',
              'VarDict':       'D',
              'MuSE':          'U',
              'LoFreq':        'L'}


mvjsdu = ''
for tool_i in tools:
    mvjsdu = mvjsdu + tools_code[tool_i]
total_num_tools = len(mvjsdu)


def p2phred(p, max_phred=float('nan')):
    '''Convert p-value to Phred-scale quality score.'''
    
    if p == 0:
        Q = max_phred        
    elif p > 0:    
        Q = -10 * math.log10(p)
        if Q > max_phred:
            Q = max_phred
    elif p == 1:
        Q = 0
    elif math.isnan(p) or p<0:
        Q = nan
                
    return Q
    

def dp4_to_gt(ref_for, ref_rev, alt_for, alt_rev):
    try:
        ref_for = int(ref_for)
    except ValueError:
        ref_for = 0
        
    try:
        ref_rev = int(ref_rev)
    except ValueError:
        ref_rev = 0
        
    try:
        alt_for = int(alt_for)
    except ValueError:
        alt_for = 0
        
    try:
        alt_rev = int(alt_rev)
    except ValueError:
        alt_rev = 0
        
    var_counts = alt_for + alt_rev
    ref_counts = ref_for + ref_rev
    
    if ref_counts == var_counts == 0:
        gt = './.'
        
    elif var_counts/(var_counts+ref_counts) > 0.85:
        gt = '1/1'
        
    elif var_counts/(var_counts+ref_counts) >= 0.05:
        gt = '0/1'
        
    else:
        gt = '0/0'
        
    return gt





with open(tsv_fn) as tsv, open(vcf_fn, 'w') as vcf:
    
    # First line is a header:
    tsv_i = tsv.readline().rstrip()
    
    tsv_header = tsv_i.split('\t')
    
    # Make the header items into indices
    for n,item in enumerate(tsv_header):
        vars()[item] = n
    
    toolcode2index = {'M': if_MuTect,
                      'V': if_VarScan2,
                      'J': if_JointSNVMix2,
                      'S': if_SomaticSniper,
                      'D': if_VarDict,
                      'U': MuSE_Tier,
                      'L': if_LoFreq}
    
    
    # Create vcf headers:
    vcf.write('##fileformat=VCFv4.1\n')
    vcf.write('##FILTER=<ID=LowQual,Description="Less confident somatic mutation calls with probability value at least {}">\n'.format(lowqual_score) )
    vcf.write('##FILTER=<ID=PASS,Description="Accept as a confident somatic mutation calls with probability value at least {}">\n'.format(pass_score) )
    vcf.write('##FILTER=<ID=REJECT,Description="Rejected as a confident somatic mutation with ONCOSCORE below 2">\n')
    vcf.write('##INFO=<ID=SOMATIC,Number=0,Type=Flag,Description="Somatic mutation in primary">\n')
    vcf.write('##INFO=<ID={COMBO},Number={NUM},Type=Integer,Description="Calling decision of the {NUM} algorithms">\n'.format(COMBO=mvjsdu, NUM=total_num_tools) )
    vcf.write('##INFO=<ID=NUM_TOOLS,Number=1,Type=Float,Description="Number of tools called it Somatic">\n')

    vcf.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
    vcf.write('##FORMAT=<ID=DP4,Number=4,Type=Integer,Description="ref forward, ref reverse, alt forward, alt reverse">\n')
    vcf.write('##FORMAT=<ID=CD4,Number=4,Type=Integer,Description="ref concordant, ref discordant, alt concordant, alt discordant">\n')
    
    vcf.write('##FORMAT=<ID=refMQ,Number=1,Type=Float,Description="average mapping score for reference reads">\n')
    vcf.write('##FORMAT=<ID=altMQ,Number=1,Type=Float,Description="average mapping score for alternate reads">\n')
    vcf.write('##FORMAT=<ID=refBQ,Number=1,Type=Float,Description="average base quality score for reference reads">\n')
    vcf.write('##FORMAT=<ID=altBQ,Number=1,Type=Float,Description="average base quality score for alternate reads">\n')
    vcf.write('##FORMAT=<ID=refNM,Number=1,Type=Float,Description="average edit distance for reference reads">\n')
    vcf.write('##FORMAT=<ID=altNM,Number=1,Type=Float,Description="average edit distance for alternate reads">\n')

    vcf.write('##FORMAT=<ID=fetSB,Number=1,Type=Float,Description="Strand bias FET">\n')
    vcf.write('##FORMAT=<ID=fetCD,Number=1,Type=Float,Description="Concordance FET">\n')
    vcf.write('##FORMAT=<ID=zMQ,Number=1,Type=Float,Description="z-score rank sum of mapping quality">\n')
    vcf.write('##FORMAT=<ID=zBQ,Number=1,Type=Float,Description="z-score rank sum of base quality">\n')

    vcf.write('##FORMAT=<ID=VAF,Number=1,Type=Float,Description="Variant Allele Frequency">\n')

    vcf.write('#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tNORMAL\tTUMOR\n' )
    
    
    # Start writing content:
    tsv_i = tsv.readline().rstrip()
    
    
    while tsv_i:
        
        tsv_item = tsv_i.split('\t')
        
        score = float( tsv_item[SCORE] )

        if phred_scaled:
            scaled_score = p2phred(1-score, max_phred = 255)
        else:
            scaled_score = score
        
        
        try:
            # Non-PASS MuSE calls are made into fractions. 
            if tsv_item[MuSE_Tier] != '1':
                if_MuSE = '0'
            else:
                if_MuSE = '1'
        except NameError:
            if_MuSE = '.'
        
        
        MVJS = []
        num_tools = 0
        for tool_i in mvjsdu:
            
            if_Tool = tsv_item[ toolcode2index[tool_i] ]
            
            if if_Tool != '1':
                if_Tool = '0'
            
            MVJS.append( if_Tool )
            num_tools = num_tools + int(if_Tool)
            
        MVJS = ','.join(MVJS)
            
        info_string = 'SOMATIC;{COMBO}={MVJSD};NUM_TOOLS={NUM_TOOLS}'.format( COMBO=mvjsdu, MVJSD=MVJS, NUM_TOOLS=num_tools )

        # NORMAL
        n_ref_mq  = tsv_item[nBAM_REF_MQ]          if tsv_item[nBAM_REF_MQ]          != 'nan' else '.'
        n_alt_mq  = tsv_item[nBAM_ALT_MQ]          if tsv_item[nBAM_ALT_MQ]          != 'nan' else '.'
        
        n_ref_bq  = tsv_item[nBAM_REF_BQ]          if tsv_item[nBAM_REF_BQ]          != 'nan' else '.'
        n_alt_bq  = tsv_item[nBAM_ALT_BQ]          if tsv_item[nBAM_ALT_BQ]          != 'nan' else '.'
        
        n_ref_nm  = tsv_item[nBAM_REF_NM]          if tsv_item[nBAM_REF_NM]          != 'nan' else '.'
        n_alt_nm  = tsv_item[nBAM_ALT_NM]          if tsv_item[nBAM_ALT_NM]          != 'nan' else '.'        
        
        n_sb      = tsv_item[nBAM_StrandBias_FET]  if tsv_item[nBAM_StrandBias_FET]  != 'nan' else '.'
        n_cd      = tsv_item[nBAM_Concordance_FET] if tsv_item[nBAM_Concordance_FET] != 'nan' else '.'
        n_bqb     = tsv_item[nBAM_Z_Ranksums_BQ]   if tsv_item[nBAM_Z_Ranksums_BQ]   != 'nan' else '.'
        n_mqb     = tsv_item[nBAM_Z_Ranksums_MQ]   if tsv_item[nBAM_Z_Ranksums_MQ]   != 'nan' else '.'
        
        n_ref_for = tsv_item[N_REF_FOR] if tsv_item[N_REF_FOR] != 'nan' else '0'
        n_ref_rev = tsv_item[N_REF_REV] if tsv_item[N_REF_REV] != 'nan' else '0'
        n_alt_for = tsv_item[N_ALT_FOR] if tsv_item[N_ALT_FOR] != 'nan' else '0'
        n_alt_rev = tsv_item[N_ALT_REV] if tsv_item[N_ALT_REV] != 'nan' else '0'
        
        n_ref_con = tsv_item[nBAM_REF_Concordant] if tsv_item[nBAM_REF_Concordant] != 'nan' else '0'
        n_ref_dis = tsv_item[nBAM_REF_Discordant] if tsv_item[nBAM_REF_Discordant] != 'nan' else '0'
        n_alt_con = tsv_item[nBAM_ALT_Concordant] if tsv_item[nBAM_ALT_Concordant] != 'nan' else '0'
        n_alt_dis = tsv_item[nBAM_ALT_Concordant] if tsv_item[nBAM_ALT_Concordant] != 'nan' else '0'
        

        # DP4toGT:
        gt = dp4_to_gt(n_ref_for, n_ref_rev, n_alt_for, n_alt_rev)
        
        # 4-number strings:
        dp4_string = ','.join(( n_ref_for, n_ref_rev, n_alt_for, n_alt_rev ))
        cd4_string = ','.join(( n_ref_con, n_ref_dis, n_alt_con, n_alt_dis ))
        
        try:
            vaf = ( int(n_alt_for) + int(n_alt_rev) ) / ( int(n_alt_for) + int(n_alt_rev) + int(n_ref_for) + int(n_ref_rev) )
        except ZeroDivisionError:
            vaf = 0
        vaf = '%.3g' % vaf
        
        sample_string1 = '{GT}:{DP4}:{CD4}:{refMQ}:{altMQ}:{refBQ}:{altBQ}:{refNM}:{altNM}:{fetSB}:{fetCD}:{zMQ}:{zBQ}:{VAF}'.format(GT=gt, DP4=dp4_string, CD4=cd4_string, refMQ=n_ref_mq, altMQ=n_alt_mq, refBQ=n_ref_bq, altBQ=n_alt_bq, refNM=n_ref_nm, altNM=n_alt_nm, fetSB=n_sb, fetCD=n_cd, zMQ=n_mqb, zBQ=n_bqb, VAF=vaf)



        ### TUMOR ###
        t_ref_mq  = tsv_item[tBAM_REF_MQ]          if tsv_item[tBAM_REF_MQ]          != 'nan' else '.'
        t_alt_mq  = tsv_item[tBAM_ALT_MQ]          if tsv_item[tBAM_ALT_MQ]          != 'nan' else '.'
        
        t_ref_bq  = tsv_item[tBAM_REF_BQ]          if tsv_item[tBAM_REF_BQ]          != 'nan' else '.'
        t_alt_bq  = tsv_item[tBAM_ALT_BQ]          if tsv_item[tBAM_ALT_BQ]          != 'nan' else '.'
        
        t_ref_nm  = tsv_item[tBAM_REF_NM]          if tsv_item[tBAM_REF_NM]          != 'nan' else '.'
        t_alt_nm  = tsv_item[tBAM_ALT_NM]          if tsv_item[tBAM_ALT_NM]          != 'nan' else '.'        
        
        t_sb      = tsv_item[tBAM_StrandBias_FET]  if tsv_item[tBAM_StrandBias_FET]  != 'nan' else '.'
        t_cd      = tsv_item[tBAM_Concordance_FET] if tsv_item[tBAM_Concordance_FET] != 'nan' else '.'        
        t_bqb     = tsv_item[tBAM_Z_Ranksums_BQ]   if tsv_item[tBAM_Z_Ranksums_BQ]   != 'nan' else '.'
        t_mqb     = tsv_item[tBAM_Z_Ranksums_MQ]   if tsv_item[tBAM_Z_Ranksums_MQ]   != 'nan' else '.'
        
        t_ref_for = tsv_item[T_REF_FOR] if tsv_item[T_REF_FOR] != 'nan' else '0'
        t_ref_rev = tsv_item[T_REF_REV] if tsv_item[T_REF_REV] != 'nan' else '0'
        t_alt_for = tsv_item[T_ALT_FOR] if tsv_item[T_ALT_FOR] != 'nan' else '0'
        t_alt_rev = tsv_item[T_ALT_REV] if tsv_item[T_ALT_REV] != 'nan' else '0'

        t_ref_con = tsv_item[tBAM_REF_Concordant] if tsv_item[tBAM_REF_Concordant] != 'nan' else '0'
        t_ref_dis = tsv_item[tBAM_REF_Discordant] if tsv_item[tBAM_REF_Discordant] != 'nan' else '0'
        t_alt_con = tsv_item[tBAM_ALT_Concordant] if tsv_item[tBAM_ALT_Concordant] != 'nan' else '0'
        t_alt_dis = tsv_item[tBAM_ALT_Concordant] if tsv_item[tBAM_ALT_Concordant] != 'nan' else '0'

        # DP4toGT:
        gt = dp4_to_gt(t_ref_for, t_ref_rev, t_alt_for, t_alt_rev)
        
        # 4-number strings:
        dp4_string = ','.join(( t_ref_for, t_ref_rev, t_alt_for, t_alt_rev ))
        cd4_string = ','.join(( t_ref_con, t_ref_dis, t_alt_con, t_alt_dis ))        
        
        
        try:
            vd  = int(t_alt_for) + int(t_alt_rev)
            vaf = vd / ( vd + int(t_ref_for) + int(t_ref_rev) )
        except ZeroDivisionError:
            vd  = 0
            vaf = 0
            
        vaf = '%.3g' % vaf

        sample_string2 = '{GT}:{DP4}:{CD4}:{refMQ}:{altMQ}:{refBQ}:{altBQ}:{refNM}:{altNM}:{fetSB}:{fetCD}:{zMQ}:{zBQ}:{VAF}'.format(GT=gt, DP4=dp4_string, CD4=cd4_string, refMQ=t_ref_mq, altMQ=t_alt_mq, refBQ=t_ref_bq, altBQ=t_alt_bq, refNM=t_ref_nm, altNM=t_alt_nm, fetSB=t_sb, fetCD=t_cd, zMQ=t_mqb, zBQ=t_bqb, VAF=vaf)

        field_string = 'GT:DP4:CD4:refMQ:altMQ:refBQ:altBQ:refNM:altNM:fetSB:fetCD:zMQ:zBQ:VAF'
        
        # PASS
        if score >= pass_score:
                        
            vcf_line = '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format( tsv_item[CHROM], tsv_item[POS], tsv_item[ID], tsv_item[REF], tsv_item[ALT], '%.4f' % scaled_score, status_code, info_string, field_string, sample_string1, sample_string2)
            
            vcf.write( vcf_line )
            
        
        # Low Qual
        elif score > lowqual_score:
            
            pass_or_reject = 'LowQual'
                            
            vcf_line = '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format( tsv_item[CHROM], tsv_item[POS], tsv_item[ID], tsv_item[REF], tsv_item[ALT], '%.4f' % scaled_score, pass_or_reject, info_string, field_string, sample_string1, sample_string2)
            
            vcf.write( vcf_line )
        
        
        # REJECT
        elif print_reject:
            
            vcf_line = '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format( tsv_item[CHROM], tsv_item[POS], tsv_item[ID], tsv_item[REF], tsv_item[ALT], '%.4f' % scaled_score, 'REJECT', info_string, field_string, sample_string1, sample_string2)
            
            vcf.write( vcf_line )

        
        tsv_i = tsv.readline().rstrip()
