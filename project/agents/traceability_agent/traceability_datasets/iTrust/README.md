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
    num_bytes: 1766557
    num_examples: 524
  download_size: 538768
  dataset_size: 1766557
- config_name: matrices
  features:
  - name: source_type
    dtype: string
  - name: target_type
    dtype: string
  splits:
  - name: matrices
    num_bytes: 51
    num_examples: 2
  download_size: 1311
  dataset_size: 51
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
    num_bytes: 2088052
    num_examples: 51352
  download_size: 294073
  dataset_size: 2088052
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
    num_bytes: 241596400
    num_examples: 51352
  download_size: 15119479
  dataset_size: 241596400
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
