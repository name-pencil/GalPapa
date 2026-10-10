"""Localize the dynamic Yui name at its message insertion point.
No save values, VM command counts, or branch targets are changed.
"""
import struct
NAME=bytes.fromhex('560300248e064201000329010000')
def literal(raw):return b'M'+struct.pack('<H',len(raw)+2)+b'"'+raw+b'"'
def expression(encode):
 # Registered display names: index 4 is Yuina, index 5 is Yui.
 return bytes.fromhex('56030024760842010005')+NAME+literal('唯依菜'.encode('cp932'))+b'=\0\0'+NAME+literal(encode('유이나'))+b'=\0\0|\0\0-\0\0'+bytes.fromhex('29010000')
def apply(original_args,targets,replacements,expression_args,command_edits,encode,commands):
 # Only expression-message commands; never rewrite the two name assignments.
 count=0;offset=0
 for pos in range(0,len(commands),4):
  opcode,argc=commands[pos],commands[pos+1]
  if opcode==110 and argc==1 and original_args[offset][3]==NAME:
   replacements[offset]=bare_expression(encode);count+=1
  offset+=argc
 return count


def bare_expression(encode):
 # Character table 127 is the engine's byte-to-string table. Slot zero is
 # empty; choose the two bytes of na only after the real-name reveal.
 condition=NAME+literal('唯依菜'.encode('cp932'))+b'=\0\0'+NAME+literal(encode('유이나'))+b'=\0\0|\0\0'
 result=literal(encode('유이'))
 for byte in encode('나'):
  result+=bytes.fromhex('560300247f00')+b'W\x02\x00'+struct.pack('<H',byte)+condition+b'*\0\0'+bytes.fromhex('29010000')+b'+\0\0'
 return result
