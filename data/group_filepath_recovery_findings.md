# Group filepath recovery findings

This report compares logged `group_xxx.md` basenames with Chroma's
top-10 filepath metadata. It does not run BGE reranking or the LLM.

- Questions checked: 50
- Resolved from Chroma top-10: 9
- Ambiguous: reranking recovery required: 20
- Not found in Chroma top-10: 0
- Skipped because no group filename was logged: 21

## Per-question findings

### 1. How much money was returned to shareholders through the buyback completed in Q3?

- Benchmark document: `FY26-Q3-ifrs-inr-press-release.pdf`
- Logged group filename(s): `group_035.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_035.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_01072025210240_Form20F_July012025_1__1_/group_035.md`

### 2. Which major cloud platform provider did Infosys announce a strategic collaboration with to accelerate enterprise generative AI adoption?

- Benchmark document: `Infosys_07012026105753_PR_07012026_9080ffe8.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 3. Who did the Board approve to be appointed as Vice Chairman of the Company on April 30, 2026?

- Benchmark document: `INFY_30042026200702_Outcome_Final_80f4d5de.pdf`
- Logged group filename(s): `group_015.md, group_019.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_015.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_015.md`
- Chroma matches for `group_019.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_019.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_019.md`

### 4. What is the target price and P/E valuation multiple assigned by ICICI Direct for Infosys?

- Benchmark document: `idirect_infosys_q4fy26.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 5. Which financial institution in Australia recently subscribed to Infosys Finacle's Digital Banking SaaS Suite?

- Benchmark document: `Infosys_20082025093726_PR_20082025_b03b0cc1.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 6. What is the name of the new subsidiary that the Board approved to be incorporated in Canada?

- Benchmark document: `Infosys_17072025221306_SEfiling_Reg30_17_c41beae9.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 7. How many equity shares were extinguished by Infosys as part of the latest buyback?

- Benchmark document: `Infosys_12122025210523_SE_Filing_Extingu_c7a02380.pdf`
- Logged group filename(s): `group_049.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_049.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_049.md`

### 8. Which authority issued a show cause notice to Infosys regarding alleged ineligible ITC refunds?

- Benchmark document: `Infosys_09102025102009_SE_filing_Reg_30__a48f4cee.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 9. On what date did Infosys submit the intimation regarding a communication for the collection of a penalty to the stock exchanges?

- Benchmark document: `Infosys_06122025165814_SEfiling_Reg30_06_d4a1c5a6.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 10. What was the total value of large deals won by Infosys in the full financial year 2026?

- Benchmark document: `FY26-Q4-earningscall.pdf`
- Logged group filename(s): `group_006.md, group_007.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_006.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_16102025160458_BM_Outcome_Oct162025/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_14012026160405_BM_Outcome_January142026/group_006.md`
- Chroma matches for `group_007.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_007.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_007.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_01072025210240_Form20F_July012025_1__1_/group_007.md`

### 11. What was the reported EPS growth in INR terms for Q4?

- Benchmark document: `Infosys_27042026203405_Transcript_April2_75ac3c61.pdf`
- Logged group filename(s): `group_007.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_007.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_007.md`

### 12. With which U.S. state's Attorney General's Office did Infosys McCamish Systems enter into an Assurance of Voluntary Compliance?

- Benchmark document: `Infosys_05082025214028_SEfiling_Reg30dis_379ff598.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 13. How many US$50 million+ clients did the company have in fiscal 2026?

- Benchmark document: `Infosys_29052026202126_Infosys_Integrate_381cbe2d.pdf`
- Logged group filename(s): `group_012.md, group_001.md, group_007.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_012.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_012.md`
- Chroma matches for `group_001.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_001.md`
- Chroma matches for `group_007.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_007.md`

### 14. On what date was the 44th Annual General Meeting held?

- Benchmark document: `Infosys_02072025225219_SEfiling_AGMtrans_44b5fa19.pdf`
- Logged group filename(s): `group_006.md, group_076.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_006.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_02072025225219_SEfiling_AGMtranscript_2025/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_30062026163341_SE_Infosys_45th_AGM_transcript/group_006.md`
- Chroma matches for `group_076.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_076.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_076.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_076.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_076.md`

### 15. What is the total penalty amount demanded from the Company by the Joint Commissioner of CGST?

- Benchmark document: `Infosys_01122025170232_SEfiling_Reg30_01_7400e312.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 16. Which specific platform is Infosys deploying for Sentara to assist with its AI initiatives?

- Benchmark document: `Infosys Limited (INFY) Partners with Sentara To Enable AI Integration and Use in Hospitals.pdf`
- Logged group filename(s): `group_004.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_004.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_004.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_004.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_004.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_004.md`

### 17. What was the total reported revenue and constant currency growth for the full year ended March 31, 2026?

- Benchmark document: `FY26-Q4-ifrs-inr-press-release.pdf`
- Logged group filename(s): `group_007.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_007.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_007.md`

### 18. Which multinational oil and gas corporation did Infosys collaborate with for sustainable AI infrastructure?

- Benchmark document: `Infosys_12022026153113_PR_12022026_aaecd035.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 19. In which country did the merger of the step-down subsidiaries In-tech Engineering services S.R.L and ProIT S.R.L.RO occur?

- Benchmark document: `Infosys_15012026125035_Reg30disclosure_1_34987b3e.pdf`
- Logged group filename(s): `group_073.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_073.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_073.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_073.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_073.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_073.md`

### 20. What is the UDIN associated with the financial statements signed by Makarand M. Joshi?

- Benchmark document: `Infosys_24042026162323_UDINFinancials_Ap_4832fded.pdf`
- Logged group filename(s): `group_001.md, group_003.md, group_052.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_001.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23072025210020_SEfiling_AuditorsreportwithUDIN/group_001.md`
- Chroma matches for `group_003.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_24042026162323_UDINFinancials_April242026/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_003.md`
- Chroma matches for `group_052.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_052.md`

### 21. How did AI solutions impact developer productivity for the global financial services company client?

- Benchmark document: `FY26-Q1-earningscall.pdf`
- Logged group filename(s): `group_002.md, group_001.md, group_004.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_002.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_17022026111455_SEfiling_InvestorAIday/group_002.md`
- Chroma matches for `group_001.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_17022026111455_SEfiling_InvestorAIday/group_001.md`
- Chroma matches for `group_004.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_004.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_004.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_004.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_004.md`

### 22. What was the free cash flow generated during Q2 FY26, and what percentage of net profit did it represent?

- Benchmark document: `FY26-Q32-earningscall.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 23. What was the sequential revenue growth percentage for the quarter?

- Benchmark document: `Infosys_28072025173504_SEfiling_Earnings_8498a008.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 24. Which bank's lending process is Infosys transforming using the nCino platform?

- Benchmark document: `Infosys_11082025152913_PR_11082025_741077cc.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 25. How will the strategic collaboration with Anthropic benefit Infosys clients?

- Benchmark document: `FY26-Q4-ifrs-inr-press-release.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 26. What was the total revenue from operations for the year ended March 31, 2025, on a consolidated basis?

- Benchmark document: `Infosys_10112025172147_SE_PublicAnnounce_922ac5e9.pdf`
- Logged group filename(s): `group_060.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_060.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_060.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_060.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_060.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_060.md`

### 27. What was the total number of equity shares of the Company remaining after the extinguishment?

- Benchmark document: `Infosys_12122025210523_SE_Filing_Extingu_c7a02380.pdf`
- Logged group filename(s): `group_049.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_049.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_049.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_049.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_049.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_049.md`

### 28. What was the consolidated Price to Earnings (P/E) ratio for the year 2026?

- Benchmark document: `Infosys_24042026162323_UDINFinancials_Ap_4832fded.pdf`
- Logged group filename(s): `group_060.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_060.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_060.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_060.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_060.md`

### 29. On which specific cloud infrastructure will the Infosys Finacle Digital Banking SaaS Suite be hosted for Uniting Financial Services?

- Benchmark document: `Infosys_20082025093726_PR_20082025_b03b0cc1.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 30. Under which specific regulation of the SEBI LODR Regulations, 2015 was the reclassification request filed?

- Benchmark document: `INFY_01052026115302_2_SubmissionofApplic_0105f974.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 31. What specific Infosys solution harnesses AI-led innovation to deliver transformative Adobe solutions that elevate brand experiences?

- Benchmark document: `Infosys_10032026130708_PR_10032026_ed1cece7.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 32. What was the average closing market price on the NSE from April 1, 2024 to March 31, 2025?

- Benchmark document: `Infosys_18112025182523_SE_letter_LoF_181_da82ccb7.pdf`
- Logged group filename(s): `group_010.md, group_045.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_010.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_18112025182523_SE_letter_LoF_18112025/group_010.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_22102025144043_SE_Draft_LOA_22102025/group_010.md`
- Chroma matches for `group_045.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_045.md`

### 33. What specific experiences are Infosys and Roland-Garros aiming to serve up with their extended partnership?

- Benchmark document: `Infosys_28052026152425_PR_28052026_ef57e394.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 34. What six areas does Infosys highlight as a "large addressable market" for its AI services?

- Benchmark document: `SP20263004173805143Infosys.pdf`
- Logged group filename(s): `group_003.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_003.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_003.md`

### 35. For what specific research contributions was Nikhil Agarwal awarded the Infosys Prize 2025 in Economics?

- Benchmark document: `Infosys_10012026223344_PR_10012026_6f19f3a2.pdf`
- Logged group filename(s): `group_006.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_006.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_16102025160458_BM_Outcome_Oct162025/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_14012026160405_BM_Outcome_January142026/group_006.md`

### 36. What specific cooling technology are Infosys and ExxonMobil advancing to make AI infrastructure more sustainable?

- Benchmark document: `Infosys_12022026153113_PR_12022026_aaecd035.pdf`
- Logged group filename(s): `group_005.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_005.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_005.md`

### 37. What specific challenges and opportunities are clients facing in the Communications and Hi-Tech verticals?

- Benchmark document: `FY26-Q32-earningscall.pdf`
- Logged group filename(s): `group_002.md, group_003.md, group_025.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_002.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_01072025210240_Form20F_July012025_1__1_/group_002.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_002.md`
- Chroma matches for `group_003.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_01072025210240_Form20F_July012025_1__1_/group_003.md`
- Chroma matches for `group_025.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_025.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_025.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_025.md`

### 38. What specific Infosys platform is being leveraged to accelerate Citizens' next-generation banking capabilities?

- Benchmark document: `Infosys_03022026180152_PR_03022026_4f9ea3bd.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 39. What was the exact nature of the violation that led to the penalty of INR 40,72,525/-?

- Benchmark document: `Infosys_02012026090317_letter_January022_2d169c17.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 40. What specific act did the Vermont DFR allege IMS violated by failing to provide timely notice of the cybersecurity event?

- Benchmark document: `Infosys_11072025182751_SEfiling_Reg30dis_10343ba6.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 41. How does the capital allocation policy of Infosys link the fiscal 2026 buyback and dividend distributions with the company's outstanding equity structure?

- Benchmark document: `INFY_30052026200807_SE_Integrated_Annual_da3970a8.pdf`
- Logged group filename(s): `group_049.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_049.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_049.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_049.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_049.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_049.md`

### 42. How does the sequential decline in DSO connect with the company's hiring trends and large deal momentum?

- Benchmark document: `Infosys_19012026222220_SEfiling_Earnings_8047afc8.pdf`
- Logged group filename(s): `group_003.md, group_001.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_003.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23072025153626_Outcome23072025/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_28072025173504_SEfiling_Earningscalltranscript_28072025/group_003.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_21102025214121_SEfiling_Earningscalltranscript_q2/group_003.md`
- Chroma matches for `group_001.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_28072025173504_SEfiling_Earningscalltranscript_28072025/group_001.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_21102025214121_SEfiling_Earningscalltranscript_q2/group_001.md`

### 43. How did the fair value of investments change across different asset classes during the fiscal year?

- Benchmark document: `Infosys_29052026201312_Infosys_Integrate_1bc456ed.pdf`
- Logged group filename(s): `group_031.md, group_010.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_031.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_031.md`
- Chroma matches for `group_010.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_14012026160405_BM_Outcome_January142026/group_010.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_16102025160458_BM_Outcome_Oct162025/group_010.md`

### 44. How did regulatory challenges and macroeconomic conditions impact Infosys's revenue and TCV in Q4?

- Benchmark document: `Infosys_27042026203405_Transcript_April2_75ac3c61.pdf`
- Logged group filename(s): `group_007.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_007.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_23042026170027_outcome/group_007.md`

### 45. How do the consolidated revenues and expenses translate into the final profitability for the six-month period ended September 30, 2025?

- Benchmark document: `Infosys_18112025182523_SE_letter_LoF_181_da82ccb7.pdf`
- Logged group filename(s): `group_042.md, group_014.md, group_026.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_042.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_16102025160458_BM_Outcome_Oct162025/group_042.md`
- Chroma matches for `group_014.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_16102025160458_BM_Outcome_Oct162025/group_014.md`
- Chroma matches for `group_026.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_16102025160458_BM_Outcome_Oct162025/group_026.md`

### 46. Based on the Form 20-F disclosures regarding changes in operations, what specific events relating to key personnel and business structure must be reported?

- Benchmark document: `INFY_15062026210015_Form20F_June152026_3602c163.pdf`
- Logged group filename(s): `group_024.md, group_017.md, group_039.md`
- Finding: **Resolved from Chroma top-10**
- Chroma matches for `group_024.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_01072025210240_Form20F_July012025_1__1_/group_024.md`
- Chroma matches for `group_017.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_15062026210015_Form20F_June152026/group_017.md`
- Chroma matches for `group_039.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_01072025210240_Form20F_July012025_1__1_/group_039.md`

### 47. How did the company navigate operational headwinds to achieve a 2.6% sequential growth in Q1?

- Benchmark document: `Infosys_28072025173504_SEfiling_Earnings_8498a008.pdf`
- Logged group filename(s): `none`
- Finding: **Skipped: no group filename**

### 48. How does the ₹18,000 crore buyback mathematically impact the company's standalone net worth and return on net worth (RONW)?

- Benchmark document: `Infosys_10112025172147_SE_PublicAnnounce_922ac5e9.pdf`
- Logged group filename(s): `group_010.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_010.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_22102025144043_SE_Draft_LOA_22102025/group_010.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_18112025182523_SE_letter_LoF_18112025/group_010.md`

### 49. What strategic financial action was validated by the postal ballot and how was it executed?

- Benchmark document: `Infosys_24042026180714_SE_Postal_ballot__2f1e79d6.pdf`
- Logged group filename(s): `group_001.md, group_005.md, group_002.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_001.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_24042026180714_SE_Postal_ballot_Notice_24042026/group_001.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_26092025155016_SE_Filing_Postal_Ballot_Notice_26092025/group_001.md`
- Chroma matches for `group_005.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_26092025155016_SE_Filing_Postal_Ballot_Notice_26092025/group_005.md`
- Chroma matches for `group_002.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_26092025155016_SE_Filing_Postal_Ballot_Notice_26092025/group_002.md`

### 50. How did the capital restructuring activity reflect on the key financial ratios and corporate governance sign-offs for fiscal 2026?

- Benchmark document: `Infosys_24042026162323_UDINFinancials_Ap_4832fded.pdf`
- Logged group filename(s): `group_006.md, group_056.md`
- Finding: **Ambiguous: reranking recovery required**
- Chroma matches for `group_006.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_006.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_006.md`
- Chroma matches for `group_056.md`:
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026201312_Infosys_Integrated_Annual_Report_2025-26/group_056.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026200807_SE_Integrated_Annual_Report_2025-26/group_056.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26/group_056.md`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files/INFY_30052026201240_SE_Integrated_Annual_Report_2025-26/group_056.md`
