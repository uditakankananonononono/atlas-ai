import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {test,expect} from 'vitest';
import {Dialog,DialogTrigger,DialogContent,DialogTitle,DialogDescription} from './dialog';
test('Radix dialog opens accessibly, closes on Escape, and returns focus',async()=>{
 const user=userEvent.setup();
 render(<Dialog><DialogTrigger>Open notes</DialogTrigger><DialogContent><DialogTitle>Node notes</DialogTitle><DialogDescription>Reviewed evidence notes</DialogDescription><input aria-label="Note field"/></DialogContent></Dialog>);
 const trigger=screen.getByRole('button',{name:'Open notes'});
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();await user.click(trigger);
 expect(screen.getByRole('dialog',{name:'Node notes'})).toBeVisible();
 expect(screen.getByRole('dialog')).toHaveAccessibleDescription('Reviewed evidence notes');
 await user.keyboard('{Escape}');await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
 await waitFor(()=>expect(trigger).toHaveFocus());
});
