import React from 'react';
import {render,screen} from '@testing-library/react';
import {expect,test,vi} from 'vitest';
import OperationsChart from './OperationsChart';
vi.mock('recharts',()=>({ResponsiveContainer:({children}:any)=><div>{children}</div>,BarChart:({data,children}:any)=><div data-testid="bars" data-values={JSON.stringify(data)}>{children}</div>,Bar:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,CartesianGrid:()=>null}));
test('never mixes unlike KPI units or invents time history',()=>{
 render(<OperationsChart data={[{label:'Count',value:3,unit:'count'},{label:'Revenue',value:90,unit:'USD'},{label:'Other count',value:7,unit:'count'}]}/>);
 expect(screen.getByLabelText('Current KPIs (count)')).toBeVisible();expect(screen.getByLabelText('Current KPIs (USD)')).toBeVisible();
 const groups=screen.getAllByTestId('bars').map(el=>JSON.parse(el.getAttribute('data-values')!));
 expect(groups).toEqual([[{label:'Count',value:3,unit:'count'},{label:'Other count',value:7,unit:'count'}],[{label:'Revenue',value:90,unit:'USD'}]]);
 expect(screen.queryByText(/trend/i)).not.toBeInTheDocument();
});
