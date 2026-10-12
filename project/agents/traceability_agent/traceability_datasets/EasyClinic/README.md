---
dataset_info:
- config_name: artifacts
  features:
  - name: id
    dtype: string
  - name: content
    dtype: string
  - name: summary
    dtype: string
  - name: layer
    dtype: string
  splits:
  - name: artifacts
    num_bytes: 191729
    num_examples: 160
  download_size: 56918
  dataset_size: 191729
- config_name: matrices
  features:
  - name: source_type
    dtype: string
  - name: target_type
    dtype: string
  splits:
  - name: matrices
    num_bytes: 40
    num_examples: 1
  download_size: 1400
  dataset_size: 40
- config_name: traces
  features:
  - name: source
    dtype: string
  - name: target
    dtype: string
  - name: label
    dtype: int64
  splits:
  - name: traces
    num_bytes: 66270
    num_examples: 2209
  download_size: 7752
  dataset_size: 66270
- config_name: train
  features:
  - name: s_text
    dtype: string
  - name: t_text
    dtype: string
  - name: label
    dtype: int64
  splits:
  - name: train
    num_bytes: 5392592
    num_examples: 2209
  download_size: 107590
  dataset_size: 5392592
configs:
- config_name: artifacts
  data_files:
  - split: artifacts
    path: artifacts/artifacts-*
- config_name: matrices
  data_files:
  - split: matrices
    path: matrices/matrices-*
- config_name: traces
  data_files:
  - split: traces
    path: traces/traces-*
- config_name: train
  data_files:
  - split: train
    path: train/train-*
---
