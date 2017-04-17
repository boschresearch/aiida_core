# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida_core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

from plum.wait import WaitOn
from aiida.orm.utils import load_workflow
from aiida.common.datastructures import wf_states
from aiida.common.lang import override
from aiida.work.globals import get_event_emitter, class_loader, REGISTRY


class WaitOnProcessTerminated(WaitOn):
    PK = "pk"

    @override
    def init(self, pk):
        super(WaitOnProcessTerminated, self).init()
        self._pk = pk

    @override
    def load_instance_state(self, bundle):
        super(WaitOnProcessTerminated, self).load_instance_state(bundle)
        self._pk = bundle[self.PK]

    @override
    def save_instance_state(self, out_state):
        super(WaitOnProcessTerminated, self).save_instance_state(out_state)
        out_state[self.PK] = self._pk
        out_state.set_class_loader(class_loader)

    @override
    def wait(self, timeout=None):
        # Need to start listening first so we don't do the following:
        # 1. REGISTRY.has_finished(..) returns False
        # <- Calculation terminates
        # 2. Start listening
        # 3. Wait forever because the calculation has finished already

        emitter = get_event_emitter()
        # Start listening to all the states we care about
        for proc_type in ['calc', 'process']:
            for state in ['stopped', 'failed']:
                evt = "{}.{}.{}".format(proc_type, self._pk, state)
                emitter.start_listening(self._calc_terminated, evt)

        if REGISTRY.has_finished(self._pk):
            try:
                self.done()
            except AssertionError:
                # already called
                pass

        try:
            return super(WaitOnProcessTerminated, self).wait(timeout=timeout)
        finally:
            emitter.stop_listening(self._calc_terminated)

    def _calc_terminated(self, emitter, event, body):
        self.done()


class WaitOnWorkflow(WaitOn):
    PK = "pk"

    def __init__(self, pk):
        super(WaitOnWorkflow, self).__init__()
        self._pk = pk

    @override
    def wait(self, timeout=None):
        # Need to start listening first so we DON'T do the following:
        # 1. REGISTRY.has_finished(..) returns False
        # <- Calculation terminates
        # 2. Start listening
        # 3. Wait forever because the calculation has finished already

        emitter = get_event_emitter()

        emitter.start_listening(
            self._workflow_finished_handler, "legacy_workflow.{}".format(self._pk))

        wf = load_workflow(pk=self._pk)
        if wf.get_state() in [wf_states.FINISHED, wf_states.ERROR]:
            try:
                self.done()
            except AssertionError:
                # already called
                pass

        try:
            return super(WaitOnWorkflow, self).wait(timeout=timeout)
        finally:
            emitter.stop_listening(self._workflow_finished_handler)

    def _workflow_finished_handler(self, emitter, event, body):
        self.done(True)

    @override
    def save_instance_state(self, out_state):
        super(WaitOnWorkflow, self).save_instance_state(out_state)
        out_state[self.PK] = self._pk
        out_state.set_class_loader(class_loader)
