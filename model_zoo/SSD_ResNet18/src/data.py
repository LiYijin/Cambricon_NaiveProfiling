# Copyright (c) 2018-2019, NVIDIA CORPORATION. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import torch
from torch.utils.data import DataLoader

from src.utils import dboxes300_coco, COCODetection
from src.utils import SSDTransformer
from src.coco import COCO

def get_train_loader(args, local_seed):
    train_annotate = os.path.join(args.data, "annotations/instances_train2017.json")
    train_coco_root = os.path.join(args.data, "train2017")

    # get_train_dataset
    dboxes = dboxes300_coco()
    train_trans = SSDTransformer(dboxes, (300, 300), val=False)
    train_coco = COCODetection(train_coco_root, train_annotate, train_trans)

    # get train dataloader
    if args.distributed:
        train_sampler = torch.utils.data.distributed.DistributedSampler(train_coco)
    else:
        train_sampler = None

    if args.data_backend == "pytorch":
        train_loader = DataLoader(train_coco,
                                    batch_size=args.batch_size,
                                    shuffle=(train_sampler is None),  # Note: distributed sampler is shuffled :(
                                    sampler=train_sampler,
                                    num_workers=args.num_workers,
                                    pin_memory=True)
    elif args.data_backend == 'dali-gpu':
        from src.coco_pipeline_mlu import COCOPipeline, DALICOCOIterator
        train_pipe = COCOPipeline(batch_size=args.batch_size,
                                  file_root=train_coco_root,
                                  annotations_file=train_annotate,
                                  default_boxes=dboxes300_coco(),
                                  device_id=args.local_rank,
                                  num_shards=args.N_gpu,
                                  output_fp16=args.pyamp,
                                  output_nhwc=False,
                                  pad_output=False,
                                  num_threads=args.num_workers, seed=local_seed, device="gpu")
        train_pipe.build()
        train_pipe.schedule_run()
        train_pipe.share_outputs()
        train_pipe.release_outputs()
        train_loader = DALICOCOIterator(train_pipe, 118287 / args.N_gpu, device="gpu")
    elif args.data_backend == 'dali-mlu':
        from src.coco_pipeline_mlu import COCOPipeline, DALICOCOIterator
        train_pipe = COCOPipeline(batch_size=args.batch_size,
                                  file_root=train_coco_root,
                                  annotations_file=train_annotate,
                                  default_boxes=dboxes300_coco(),
                                  device_id=args.local_rank,
                                  num_shards=args.N_gpu,
                                  output_fp16=args.pyamp,
                                  output_nhwc=False,
                                  pad_output=False,
                                  num_threads=args.num_workers, seed=local_seed, device="gpu")
        train_pipe.build()
        train_pipe.schedule_run()
        train_pipe.share_outputs()
        train_pipe.release_outputs()
        train_loader = DALICOCOIterator(train_pipe, 118287 / args.N_gpu, device="mlu")
    return train_loader


def get_val_dataset(args):
    dboxes = dboxes300_coco()
    val_trans = SSDTransformer(dboxes, (300, 300), val=True)

    val_annotate = os.path.join(args.data, "annotations/instances_val2017.json")
    val_coco_root = os.path.join(args.data, "val2017")

    val_coco = COCODetection(val_coco_root, val_annotate, val_trans)
    return val_coco


def get_val_dataloader(dataset, args):
    if args.distributed:
        val_sampler = torch.utils.data.distributed.DistributedSampler(dataset)
    else:
        val_sampler = None

    val_dataloader = DataLoader(dataset,
                                batch_size=args.eval_batch_size,
                                shuffle=False,  # Note: distributed sampler is shuffled :(
                                sampler=val_sampler,
                                num_workers=args.num_workers,
                                pin_memory=True)

    return val_dataloader

def get_coco_ground_truth(args):
    val_annotate = os.path.join(args.data, "annotations/instances_val2017.json")
    cocoGt = COCO(annotation_file=val_annotate)
    return cocoGt
